from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.executable_support import (
    MechanismMutationKind,
    PublicWitnessStep,
    TypedAnswerProjectionContract,
)
from trusted_synthesis.hashing import canonical_hash

EXECUTABLE_TASK_CONTRACT_VERSION = "executable_task_contract.v1"
EXECUTABLE_TASK_PACKAGE_VERSION = "executable_task_package.v1"
EXECUTABLE_TASK_WITNESS_VERSION = "executable_task_witness.v1"
STATIC_MODEL_AUTHORITY_PATH_VERSION = "static_model_authority_path.v1"

IntendedTaskUse = Literal["capability_measurement", "vtdo_multistate_candidate"]
StaticPathStatus = Literal["not_required", "passed", "blocked"]
AdmissionStatus = Literal[
    "blocked",
    "capability_ready",
    "static_vtdo_ready",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExecutableTaskSemanticSource(FrozenModel):
    """Pre-identity semantic source from which every task-facing contract is compiled."""

    semantic_source_id: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    source_task_artifact_ids: tuple[str, ...] = Field(min_length=1)
    evidence_version_ids: tuple[str, ...] = Field(min_length=1)
    evidence_bundle_hash: str = Field(min_length=1)
    public_corpus_hash: str = Field(min_length=1)
    proof_graph_hash: str = Field(min_length=1)
    task_program_hash: str = Field(min_length=1)
    retrieval_scope_hash: str = Field(min_length=1)
    answer_source_spec_hash: str = Field(min_length=1)
    mechanism_source_spec_hash: str = Field(min_length=1)
    intended_use: IntendedTaskUse
    schema_version: str = EXECUTABLE_TASK_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_source(self) -> ExecutableTaskSemanticSource:
        if self.source_task_artifact_ids != tuple(sorted(set(self.source_task_artifact_ids))):
            raise ValueError("executable task source artifacts are not canonical")
        if self.evidence_version_ids != tuple(sorted(set(self.evidence_version_ids))):
            raise ValueError("executable task Evidence versions are not canonical")
        if self.semantic_source_id != executable_task_semantic_source_id(self):
            raise ValueError("executable task semantic source identity is invalid")
        return self


class ToolClosureContract(FrozenModel):
    closure_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    program_tool_ids: tuple[str, ...] = Field(min_length=1)
    verification_tool_ids: tuple[str, ...] = Field(min_length=1)
    recovery_tool_ids: tuple[str, ...] = ()
    required_tool_ids: tuple[str, ...] = Field(min_length=1)
    allowed_tool_ids: tuple[str, ...] = Field(min_length=1)
    status: Literal["passed"] = "passed"
    schema_version: str = EXECUTABLE_TASK_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_closure(self) -> ToolClosureContract:
        groups = (
            self.program_tool_ids,
            self.verification_tool_ids,
            self.recovery_tool_ids,
            self.required_tool_ids,
            self.allowed_tool_ids,
        )
        if any(group != tuple(sorted(set(group))) for group in groups):
            raise ValueError("executable task tool identities are not canonical")
        expected_required = tuple(
            sorted(
                set(self.program_tool_ids)
                | set(self.verification_tool_ids)
                | set(self.recovery_tool_ids)
            )
        )
        if self.required_tool_ids != expected_required:
            raise ValueError("required tool closure differs from its component union")
        if not set(self.required_tool_ids) <= set(self.allowed_tool_ids):
            raise ValueError("required tools are not a subset of Allowed Tools")
        if self.closure_id != tool_closure_contract_id(self):
            raise ValueError("tool closure contract identity is invalid")
        return self


class BoundEvidenceSupportSet(FrozenModel):
    support_set_id: str = Field(min_length=1)
    kind: Literal["sufficient", "invalid"]
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    rationale_code: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_support_set(self) -> BoundEvidenceSupportSet:
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("bound Evidence support IDs are not canonical")
        if self.support_set_id != bound_evidence_support_set_id(self):
            raise ValueError("bound Evidence support-set identity is invalid")
        return self


class BoundEvidenceSupportLattice(FrozenModel):
    """Pre-task lattice consumed by the bound Verifier, without a Joint-ID cycle."""

    lattice_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    necessary_evidence_ids: tuple[str, ...] = Field(min_length=1)
    sufficient_support_sets: tuple[BoundEvidenceSupportSet, ...] = Field(min_length=1)
    invalid_support_sets: tuple[BoundEvidenceSupportSet, ...] = ()
    semantic_alternative_search_complete: bool
    unique_support_proven: bool
    exact_equality_required: bool
    verifier_membership_rule: Literal["contains_registered_sufficient_set"] = (
        "contains_registered_sufficient_set"
    )
    schema_version: str = EXECUTABLE_TASK_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_lattice(self) -> BoundEvidenceSupportLattice:
        if self.necessary_evidence_ids != tuple(sorted(set(self.necessary_evidence_ids))):
            raise ValueError("bound lattice necessary Evidence is not canonical")
        if any(item.kind != "sufficient" for item in self.sufficient_support_sets):
            raise ValueError("bound lattice sufficient sets contain another kind")
        if any(item.kind != "invalid" for item in self.invalid_support_sets):
            raise ValueError("bound lattice invalid sets contain another kind")
        identities = tuple(
            item.support_set_id
            for item in (*self.sufficient_support_sets, *self.invalid_support_sets)
        )
        if len(identities) != len(set(identities)):
            raise ValueError("bound lattice reuses a support-set identity")
        if self.exact_equality_required and not (
            self.semantic_alternative_search_complete
            and self.unique_support_proven
            and len(self.sufficient_support_sets) == 1
        ):
            raise ValueError("bound lattice exact equality lacks a uniqueness proof")
        if self.lattice_id != bound_evidence_support_lattice_id(self):
            raise ValueError("bound Evidence support lattice identity is invalid")
        return self


class CitationCompletenessContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    evidence_support_lattice_id: str = Field(min_length=1)
    completeness_rule: Literal[
        "cited_support_contains_path_required_and_registered_sufficient_set"
    ] = "cited_support_contains_path_required_and_registered_sufficient_set"
    exact_gold_equality_forbidden: bool
    schema_version: str = EXECUTABLE_TASK_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> CitationCompletenessContract:
        if self.contract_id != citation_completeness_contract_id(self):
            raise ValueError("Citation completeness contract identity is invalid")
        return self


class MechanismCausalContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    target_mechanism_id: str = Field(min_length=1)
    required_mutation_kinds: tuple[MechanismMutationKind, ...] = Field(min_length=1)
    required_witness_event_ids: tuple[str, ...] = Field(min_length=1)
    closure_requirements: tuple[str, ...] = Field(min_length=1)
    decision_authority: Literal["model"] = "model"
    mutation_target_rule: Literal["exact_target_contract"] = "exact_target_contract"
    irreparability_policy: str = Field(min_length=1)
    counterfactual_verifier_id: str = Field(min_length=1)
    counterfactual_verifier_version: str = Field(min_length=1)
    schema_version: str = EXECUTABLE_TASK_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> MechanismCausalContract:
        if len(self.required_mutation_kinds) != len(set(self.required_mutation_kinds)):
            raise ValueError("mechanism causal mutation kinds are duplicated")
        if self.required_witness_event_ids != tuple(sorted(set(self.required_witness_event_ids))):
            raise ValueError("mechanism witness events are not canonical")
        if self.closure_requirements != tuple(sorted(set(self.closure_requirements))):
            raise ValueError("mechanism closure requirements are not canonical")
        if self.contract_id != mechanism_causal_contract_id(self):
            raise ValueError("mechanism causal contract identity is invalid")
        return self


class PublicRuntimeContract(FrozenModel):
    contract_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    tool_closure_contract_id: str = Field(min_length=1)
    environment_manifest_hash: str = Field(min_length=1)
    runtime_implementation_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    allowed_tool_ids: tuple[str, ...] = Field(min_length=1)
    network_policy: Literal["forbidden"] = "forbidden"
    maximum_tool_calls: int = Field(ge=1)
    maximum_failed_tool_calls: int = Field(ge=0)
    schema_version: str = EXECUTABLE_TASK_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> PublicRuntimeContract:
        if self.allowed_tool_ids != tuple(sorted(set(self.allowed_tool_ids))):
            raise ValueError("public Runtime Allowed Tools are not canonical")
        if self.maximum_failed_tool_calls >= self.maximum_tool_calls:
            raise ValueError("failed tool-call budget must be smaller than total budget")
        if self.contract_id != public_runtime_contract_id(self):
            raise ValueError("public Runtime contract identity is invalid")
        return self


class ExecutableVerifierBinding(FrozenModel):
    binding_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    answer_projection_contract_id: str = Field(min_length=1)
    evidence_support_lattice_id: str = Field(min_length=1)
    citation_contract_id: str = Field(min_length=1)
    public_runtime_contract_id: str = Field(min_length=1)
    mechanism_contract_id: str = Field(min_length=1)
    verifier_implementation_id: str = Field(min_length=1)
    verifier_version: str = Field(min_length=1)
    evidence_acceptance_rule: Literal["registered_sufficient_set_membership"] = (
        "registered_sufficient_set_membership"
    )
    exact_gold_equality_required: bool
    schema_version: str = EXECUTABLE_TASK_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_binding(self) -> ExecutableVerifierBinding:
        if self.binding_id != executable_verifier_binding_id(self):
            raise ValueError("executable Verifier binding identity is invalid")
        return self


class ExecutableTaskPackage(FrozenModel):
    """New task identity binding every executable-support contract before admission."""

    package_id: str = Field(min_length=1)
    semantic_source: ExecutableTaskSemanticSource
    task: TaskPackage
    tool_closure: ToolClosureContract
    answer_projection: TypedAnswerProjectionContract
    evidence_support_lattice: BoundEvidenceSupportLattice
    citation_contract: CitationCompletenessContract
    public_runtime_contract: PublicRuntimeContract
    mechanism_contract: MechanismCausalContract
    verifier_binding: ExecutableVerifierBinding
    schema_version: str = EXECUTABLE_TASK_PACKAGE_VERSION

    @model_validator(mode="after")
    def validate_package(self) -> ExecutableTaskPackage:
        source_id = self.semantic_source.semantic_source_id
        source_bound = (
            self.tool_closure.semantic_source_id,
            self.answer_projection.task_id,
            self.evidence_support_lattice.semantic_source_id,
            self.citation_contract.semantic_source_id,
            self.public_runtime_contract.semantic_source_id,
            self.mechanism_contract.semantic_source_id,
            self.verifier_binding.semantic_source_id,
        )
        if any(item != source_id for item in source_bound):
            raise ValueError("executable task contracts were compiled from different sources")
        if self.task.task_id != self.package_id:
            raise ValueError("executable task package and TaskPackage identities differ")
        if tuple(sorted(self.task.public.allowed_tools)) != self.tool_closure.allowed_tool_ids:
            raise ValueError("TaskPackage Allowed Tools differ from the closure contract")
        if self.public_runtime_contract.allowed_tool_ids != self.tool_closure.allowed_tool_ids:
            raise ValueError("public Runtime differs from the tool closure")
        if self.public_runtime_contract.tool_closure_contract_id != self.tool_closure.closure_id:
            raise ValueError("public Runtime is detached from tool closure")
        if (
            self.citation_contract.evidence_support_lattice_id
            != self.evidence_support_lattice.lattice_id
        ):
            raise ValueError("Citation contract is detached from the Evidence lattice")
        binding_values = {
            "answer_projection_contract_id": self.answer_projection.contract_id,
            "evidence_support_lattice_id": self.evidence_support_lattice.lattice_id,
            "citation_contract_id": self.citation_contract.contract_id,
            "public_runtime_contract_id": self.public_runtime_contract.contract_id,
            "mechanism_contract_id": self.mechanism_contract.contract_id,
        }
        if any(
            getattr(self.verifier_binding, key) != value for key, value in binding_values.items()
        ):
            raise ValueError("executable Verifier does not bind the packaged contracts")
        if (
            self.verifier_binding.exact_gold_equality_required
            != self.evidence_support_lattice.exact_equality_required
        ):
            raise ValueError("Verifier exact-equality semantics differ from the lattice")
        public_bindings = self.task.public.metadata.get("executable_support_bindings")
        expected_public = {
            "answer_projection_contract_id": self.answer_projection.contract_id,
            "citation_contract_id": self.citation_contract.contract_id,
            "intended_use": self.semantic_source.intended_use,
            "public_runtime_contract_id": self.public_runtime_contract.contract_id,
            "tool_closure_contract_id": self.tool_closure.closure_id,
        }
        if public_bindings != expected_public:
            raise ValueError("Task Public Spec does not expose the frozen public bindings")
        oracle_bindings = self.task.oracle.selection_contract.get("executable_support_bindings")
        expected_oracle = {
            **expected_public,
            "evidence_support_lattice_id": self.evidence_support_lattice.lattice_id,
            "mechanism_contract_id": self.mechanism_contract.contract_id,
            "semantic_source_id": source_id,
            "verifier_binding_id": self.verifier_binding.binding_id,
        }
        if oracle_bindings != expected_oracle:
            raise ValueError("Task Oracle Contract does not bind executable support")
        if self.package_id != executable_task_package_id(self):
            raise ValueError("executable task package identity is invalid")
        return self


class BoundPublicExecutableWitness(FrozenModel):
    witness_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    public_runtime_contract_id: str = Field(min_length=1)
    path_strategy_id: str = Field(min_length=1)
    steps: tuple[PublicWitnessStep, ...] = Field(min_length=1)
    selected_evidence_ids: tuple[str, ...] = Field(min_length=1)
    verification_support_ids: tuple[str, ...] = Field(min_length=1)
    cited_evidence_ids: tuple[str, ...] = Field(min_length=1)
    satisfying_support_set_id: str = Field(min_length=1)
    mechanism_event_ids: tuple[str, ...] = Field(min_length=1)
    normalized_answer: dict[str, object]
    normalized_answer_hash: str = Field(min_length=1)
    independent_verifier_report_hash: str = Field(min_length=1)
    only_public_inputs: bool
    only_allowed_tools: bool
    operation_lineage_complete: bool
    evidence_support_complete: bool
    verification_complete: bool
    answer_projection_complete: bool
    citation_complete: bool
    mechanism_complete: bool
    no_postcompletion_violation: bool
    full_validity_passed: bool
    failure_reasons: tuple[str, ...]
    hidden_from_model: Literal[True] = True
    compiler_generated: Literal[True] = True
    model_generated: Literal[False] = False
    schema_version: str = EXECUTABLE_TASK_WITNESS_VERSION

    @model_validator(mode="after")
    def validate_witness(self) -> BoundPublicExecutableWitness:
        if tuple(item.step_index for item in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError("bound public witness steps are not contiguous")
        canonical_sets = (
            self.selected_evidence_ids,
            self.verification_support_ids,
            self.cited_evidence_ids,
            self.mechanism_event_ids,
        )
        if any(group != tuple(sorted(set(group))) for group in canonical_sets):
            raise ValueError("bound public witness identities are not canonical")
        if not set(self.cited_evidence_ids) <= set(self.selected_evidence_ids):
            raise ValueError("bound public witness cites unselected Evidence")
        if self.normalized_answer_hash != canonical_hash(
            self.normalized_answer, prefix="executable_witness_answer:"
        ):
            raise ValueError("bound public witness answer hash is invalid")
        checks = (
            self.only_public_inputs,
            self.only_allowed_tools,
            self.operation_lineage_complete,
            self.evidence_support_complete,
            self.verification_complete,
            self.answer_projection_complete,
            self.citation_complete,
            self.mechanism_complete,
            self.no_postcompletion_violation,
        )
        if self.full_validity_passed != all(checks):
            raise ValueError("bound public witness validity is inconsistent")
        if bool(self.failure_reasons) == self.full_validity_passed:
            raise ValueError("bound public witness failure reasons are inconsistent")
        if self.witness_id != bound_public_executable_witness_id(self):
            raise ValueError("bound public executable witness identity is invalid")
        return self


class StaticModelAuthorityPath(FrozenModel):
    path_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    compiler_witness_id: str = Field(min_length=1)
    path_strategy_id: str = Field(min_length=1)
    model_owned_decision_signature: str = Field(min_length=1)
    behavior_signature: str = Field(min_length=1)
    quotient_state_id: str = Field(min_length=1)
    scaffold_surface_signature: str = Field(min_length=1)
    full_validity_passed: Literal[True] = True
    decision_authority: Literal["model"] = "model"
    materialization_origin: Literal["compiler"] = "compiler"
    model_generated: Literal[False] = False
    empirical_reachability: Literal["unmeasured"] = "unmeasured"
    schema_version: str = STATIC_MODEL_AUTHORITY_PATH_VERSION

    @model_validator(mode="after")
    def validate_path(self) -> StaticModelAuthorityPath:
        if self.path_id != static_model_authority_path_id(self):
            raise ValueError("static model-authority path identity is invalid")
        return self


class StaticModelAuthorityPathCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    intended_use: IntendedTaskUse
    minimum_path_count: Literal[3] = 3
    paths: tuple[StaticModelAuthorityPath, ...] = ()
    status: StaticPathStatus
    empirical_reachability_evaluated: Literal[False] = False
    failure_reasons: tuple[str, ...]
    schema_version: str = STATIC_MODEL_AUTHORITY_PATH_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> StaticModelAuthorityPathCatalog:
        if any(item.task_package_id != self.task_package_id for item in self.paths):
            raise ValueError("static path catalog contains another task")
        unique_decisions = {item.model_owned_decision_signature for item in self.paths}
        unique_behaviors = {item.behavior_signature for item in self.paths}
        unique_states = {item.quotient_state_id for item in self.paths}
        passed = (
            len(self.paths) >= self.minimum_path_count
            and len(unique_decisions) >= self.minimum_path_count
            and len(unique_behaviors) >= self.minimum_path_count
            and len(unique_states) >= self.minimum_path_count
            and len({item.path_id for item in self.paths}) == len(self.paths)
        )
        expected: StaticPathStatus
        if self.intended_use == "capability_measurement":
            expected = "not_required"
            if self.paths:
                raise ValueError("capability-only task unexpectedly carries VTDO paths")
        else:
            expected = "passed" if passed else "blocked"
        if self.status != expected:
            raise ValueError("static model-authority path status is inconsistent")
        if bool(self.failure_reasons) != (expected == "blocked"):
            raise ValueError("static model-authority path failures are inconsistent")
        if self.catalog_id != static_model_authority_path_catalog_id(self):
            raise ValueError("static model-authority path catalog identity is invalid")
        return self


class ExecutableTaskAdmission(FrozenModel):
    admission_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    intended_use: IntendedTaskUse
    public_witness_id: str = Field(min_length=1)
    mechanism_necessity_artifact_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    package_bindings_passed: bool
    public_witness_passed: bool
    mechanism_necessity_passed: bool
    static_path_support_passed: bool
    capability_measurement_eligible: bool
    static_vtdo_candidate_eligible: bool
    empirical_reachability_evaluated: Literal[False] = False
    status: AdmissionStatus
    blockers: tuple[str, ...]
    schema_version: str = EXECUTABLE_TASK_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_admission(self) -> ExecutableTaskAdmission:
        expected_capability = all(
            (
                self.package_bindings_passed,
                self.public_witness_passed,
                self.mechanism_necessity_passed,
            )
        )
        expected_vtdo = (
            expected_capability
            and self.intended_use == "vtdo_multistate_candidate"
            and self.static_path_support_passed
        )
        if self.capability_measurement_eligible != expected_capability:
            raise ValueError("executable task capability eligibility is inconsistent")
        if self.static_vtdo_candidate_eligible != expected_vtdo:
            raise ValueError("executable task static VTDO eligibility is inconsistent")
        expected_status: AdmissionStatus = (
            "static_vtdo_ready"
            if expected_vtdo
            else "capability_ready"
            if expected_capability and self.intended_use == "capability_measurement"
            else "blocked"
        )
        if self.status != expected_status:
            raise ValueError("executable task admission status is inconsistent")
        if bool(self.blockers) != (expected_status == "blocked"):
            raise ValueError("executable task admission blockers are inconsistent")
        if self.admission_id != executable_task_admission_id(self):
            raise ValueError("executable task admission identity is invalid")
        return self


def matching_sufficient_support_set(
    lattice: BoundEvidenceSupportLattice,
    evidence_ids: tuple[str, ...],
) -> BoundEvidenceSupportSet | None:
    observed = set(evidence_ids)
    matches = [
        item for item in lattice.sufficient_support_sets if set(item.evidence_ids) <= observed
    ]
    return min(
        matches,
        key=lambda item: (len(item.evidence_ids), item.support_set_id),
        default=None,
    )


def executable_task_semantic_source_id(value: ExecutableTaskSemanticSource) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"semantic_source_id"}),
        prefix="executable_task_semantic_source:",
    )


def tool_closure_contract_id(value: ToolClosureContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"closure_id"}),
        prefix="tool_closure_contract:",
    )


def bound_evidence_support_set_id(value: BoundEvidenceSupportSet) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"support_set_id"}),
        prefix="bound_evidence_support_set:",
    )


def bound_evidence_support_lattice_id(value: BoundEvidenceSupportLattice) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"lattice_id"}),
        prefix="bound_evidence_support_lattice:",
    )


def citation_completeness_contract_id(value: CitationCompletenessContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="citation_completeness_contract:",
    )


def mechanism_causal_contract_id(value: MechanismCausalContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="mechanism_causal_contract:",
    )


def public_runtime_contract_id(value: PublicRuntimeContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="public_runtime_contract:",
    )


def executable_verifier_binding_id(value: ExecutableVerifierBinding) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"binding_id"}),
        prefix="executable_verifier_binding:",
    )


def executable_task_package_id(value: ExecutableTaskPackage) -> str:
    payload = value.model_dump(mode="json", exclude={"package_id"})
    payload["task"]["task_id"] = "self"
    payload["task"]["public"]["task_id"] = "self"
    payload["task"]["oracle"]["task_id"] = "self"
    return canonical_hash(payload, prefix="executable_task_package:")


def bound_public_executable_witness_id(value: BoundPublicExecutableWitness) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"witness_id"}),
        prefix="bound_public_executable_witness:",
    )


def static_model_authority_path_id(value: StaticModelAuthorityPath) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"path_id"}),
        prefix="static_model_authority_path:",
    )


def static_model_authority_path_catalog_id(
    value: StaticModelAuthorityPathCatalog,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"catalog_id"}),
        prefix="static_model_authority_path_catalog:",
    )


def executable_task_admission_id(value: ExecutableTaskAdmission) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"admission_id"}),
        prefix="executable_task_admission:",
    )
