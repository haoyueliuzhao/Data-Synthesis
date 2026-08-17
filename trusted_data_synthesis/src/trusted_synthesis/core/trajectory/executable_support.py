from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.hashing import canonical_hash

EXECUTABLE_SUPPORT_CONTRACT_VERSION_V1 = "executable_support_contract.v1"
EXECUTABLE_SUPPORT_CONTRACT_VERSION = "executable_support_contract.v2"

ProjectionView = Literal[
    "public_output_instruction",
    "oracle_normalizer",
    "human_renderer",
    "verifier_matcher",
]
SupportSetKind = Literal["sufficient", "invalid"]
MechanismMutationKind = Literal["delete", "replace", "bypass"]
TaskUse = Literal["blocked", "capability_measurement", "vtdo_multistate"]

PROJECTION_VIEWS: tuple[ProjectionView, ...] = (
    "public_output_instruction",
    "oracle_normalizer",
    "human_renderer",
    "verifier_matcher",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ProjectionViewBinding(FrozenModel):
    view: ProjectionView
    implementation_id: str = Field(min_length=1)
    implementation_version: str = Field(min_length=1)
    source_spec_hash: str = Field(min_length=1)


class TypedAnswerProjectionContract(FrozenModel):
    """One source specification compiled into all answer-facing views."""

    contract_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    source_task_hash: str = Field(min_length=1)
    required_result_fields: tuple[str, ...] = Field(min_length=1)
    allowed_result_fields: tuple[str, ...] = Field(min_length=1)
    internal_reference_projection: dict[str, str]
    public_reference_labels: tuple[str, ...]
    public_output_instruction: str = Field(min_length=1)
    source_spec_hash: str = Field(min_length=1)
    view_bindings: tuple[ProjectionViewBinding, ...] = Field(min_length=4, max_length=4)
    schema_version: str = EXECUTABLE_SUPPORT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_contract(self) -> TypedAnswerProjectionContract:
        if len(self.required_result_fields) != len(set(self.required_result_fields)):
            raise ValueError("answer projection required fields are duplicated")
        if len(self.allowed_result_fields) != len(set(self.allowed_result_fields)):
            raise ValueError("answer projection allowed fields are duplicated")
        if not set(self.required_result_fields) <= set(self.allowed_result_fields):
            raise ValueError("answer projection required fields are not allowed")
        expected_labels = tuple(sorted(set(self.internal_reference_projection.values())))
        if self.public_reference_labels != expected_labels:
            raise ValueError("answer projection public labels differ from the source map")
        if tuple(item.view for item in self.view_bindings) != PROJECTION_VIEWS:
            raise ValueError("answer projection views are incomplete or reordered")
        expected_source_hash = answer_projection_source_spec_hash(self)
        if self.source_spec_hash != expected_source_hash:
            raise ValueError("answer projection source specification hash is invalid")
        if any(item.source_spec_hash != expected_source_hash for item in self.view_bindings):
            raise ValueError("answer projection views were compiled from different sources")
        if self.public_output_instruction != render_public_output_instruction(
            self.required_result_fields,
            self.public_reference_labels,
        ):
            raise ValueError("answer projection public instruction is not source-derived")
        if self.contract_id != typed_answer_projection_contract_id(self):
            raise ValueError("typed answer projection contract identity is invalid")
        return self


class EvidenceSupportSet(FrozenModel):
    support_set_id: str = Field(min_length=1)
    kind: SupportSetKind
    evidence_ids: tuple[str, ...] = Field(min_length=1)
    rationale_code: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_support_set(self) -> EvidenceSupportSet:
        if self.evidence_ids != tuple(sorted(set(self.evidence_ids))):
            raise ValueError("Evidence support set IDs must be sorted and unique")
        if self.support_set_id != evidence_support_set_id(self):
            raise ValueError("Evidence support set identity is invalid")
        return self


class EvidenceSupportLattice(FrozenModel):
    """Hidden support policy; exact equality is legal only after uniqueness proof."""

    lattice_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    necessary_evidence_ids: tuple[str, ...] = Field(min_length=1)
    sufficient_support_sets: tuple[EvidenceSupportSet, ...] = Field(min_length=1)
    invalid_support_sets: tuple[EvidenceSupportSet, ...] = ()
    semantic_alternative_search_complete: bool
    unique_support_proven: bool
    exact_equality_required: bool
    current_verifier_bound: bool
    binding_status: Literal["bound", "requires_verifier_binding"]
    schema_version: str = EXECUTABLE_SUPPORT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_lattice(self) -> EvidenceSupportLattice:
        if self.necessary_evidence_ids != tuple(sorted(set(self.necessary_evidence_ids))):
            raise ValueError("necessary Evidence IDs must be sorted and unique")
        if any(item.kind != "sufficient" for item in self.sufficient_support_sets):
            raise ValueError("Evidence lattice sufficient sets contain another kind")
        if any(item.kind != "invalid" for item in self.invalid_support_sets):
            raise ValueError("Evidence lattice invalid sets contain another kind")
        all_ids = tuple(
            item.support_set_id
            for item in (*self.sufficient_support_sets, *self.invalid_support_sets)
        )
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("Evidence lattice reuses a support-set identity")
        if self.exact_equality_required and not (
            self.semantic_alternative_search_complete
            and self.unique_support_proven
            and len(self.sufficient_support_sets) == 1
        ):
            raise ValueError("exact Evidence equality lacks a completed uniqueness proof")
        expected_binding = "bound" if self.current_verifier_bound else "requires_verifier_binding"
        if self.binding_status != expected_binding:
            raise ValueError("Evidence lattice verifier binding status is inconsistent")
        if self.lattice_id != evidence_support_lattice_id(self):
            raise ValueError("Evidence support lattice identity is invalid")
        return self


class PublicWitnessStep(FrozenModel):
    step_index: int = Field(ge=1)
    tool_id: str = Field(min_length=1)
    call_hash: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    observation_content_hash: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()
    operation_ref: str | None = None
    normalized_operation_ref: str | None = None


class PublicExecutableWitnessArtifact(FrozenModel):
    """Model-hidden existential proof that the public task can be solved."""

    witness_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    environment_manifest_hash: str = Field(min_length=1)
    public_projection_hash: str = Field(min_length=1)
    allowed_tools: tuple[str, ...] = Field(min_length=1)
    steps: tuple[PublicWitnessStep, ...] = ()
    selected_evidence_ids: tuple[str, ...] = ()
    verification_support_ids: tuple[str, ...] = ()
    cited_evidence_ids: tuple[str, ...] = ()
    citation_complete: bool | None = None
    normalized_answer_hash: str = Field(min_length=1)
    independent_verifier_report_hash: str = Field(min_length=1)
    only_public_inputs: bool
    only_allowed_tools: bool
    operation_lineage_complete: bool
    evidence_support_complete: bool
    verification_complete: bool
    answer_projection_complete: bool
    full_validity_passed: bool
    failure_reasons: tuple[str, ...]
    hidden_from_model: Literal[True] = True
    model_owned_path: Literal[False] = False
    schema_version: str = EXECUTABLE_SUPPORT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_witness(self) -> PublicExecutableWitnessArtifact:
        if tuple(item.step_index for item in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError("public witness steps are not contiguous")
        if len({item.observation_id for item in self.steps}) != len(self.steps):
            raise ValueError("public witness reuses an observation")
        if not set(item.tool_id for item in self.steps) <= set(self.allowed_tools):
            raise ValueError("public witness step uses a disallowed tool")
        if self.cited_evidence_ids != tuple(sorted(set(self.cited_evidence_ids))):
            raise ValueError("public witness citations must be sorted and unique")
        if not set(self.cited_evidence_ids) <= set(self.selected_evidence_ids):
            raise ValueError("public witness cites Evidence it did not select")
        if self.schema_version == EXECUTABLE_SUPPORT_CONTRACT_VERSION_V1:
            if self.cited_evidence_ids or self.citation_complete is not None:
                raise ValueError("v1 public witness cannot carry a v2 citation attestation")
            citation_valid = True
        elif self.schema_version == EXECUTABLE_SUPPORT_CONTRACT_VERSION:
            if self.citation_complete is None:
                raise ValueError("v2 public witness requires a citation attestation")
            if self.citation_complete and not self.cited_evidence_ids:
                raise ValueError("complete public witness citation set cannot be empty")
            citation_valid = self.citation_complete
        else:
            raise ValueError("public witness schema version is unsupported")
        expected_valid = all(
            (
                self.only_public_inputs,
                self.only_allowed_tools,
                self.operation_lineage_complete,
                self.evidence_support_complete,
                self.verification_complete,
                self.answer_projection_complete,
                citation_valid,
            )
        )
        if self.full_validity_passed != expected_valid:
            raise ValueError("public witness validity is inconsistent")
        if bool(self.failure_reasons) == self.full_validity_passed:
            raise ValueError("public witness failure reasons are inconsistent")
        if self.witness_id != public_executable_witness_id(self):
            raise ValueError("public executable witness identity is invalid")
        return self


class MechanismCounterfactualResult(FrozenModel):
    result_id: str = Field(min_length=1)
    mutation_kind: MechanismMutationKind
    mutation_target: str = Field(min_length=1)
    mutated_trace_hash: str = Field(min_length=1)
    target_mechanism_absent: Literal[True] = True
    full_validity_passed: Literal[False] = False
    independent_verifier_report_hash: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_result(self) -> MechanismCounterfactualResult:
        if self.result_id != mechanism_counterfactual_result_id(self):
            raise ValueError("mechanism counterfactual identity is invalid")
        return self


class MechanismNecessityArtifact(FrozenModel):
    artifact_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    public_witness_id: str = Field(min_length=1)
    target_mechanism_id: str = Field(min_length=1)
    required_mutation_kinds: tuple[MechanismMutationKind, ...] = Field(min_length=1)
    counterfactual_results: tuple[MechanismCounterfactualResult, ...] = ()
    closure_checks: dict[str, bool] = Field(min_length=1)
    mechanism_observed_in_witness: bool
    status: Literal["passed", "blocked"]
    failure_reasons: tuple[str, ...]
    schema_version: str = EXECUTABLE_SUPPORT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_necessity(self) -> MechanismNecessityArtifact:
        if len(self.required_mutation_kinds) != len(set(self.required_mutation_kinds)):
            raise ValueError("mechanism necessity mutation kinds are duplicated")
        observed_kinds = {item.mutation_kind for item in self.counterfactual_results}
        mutations_complete = set(self.required_mutation_kinds) <= observed_kinds
        if any(
            item.mutation_target != self.target_mechanism_id for item in self.counterfactual_results
        ):
            raise ValueError("mechanism counterfactual targets another mechanism")
        expected_passed = bool(
            self.mechanism_observed_in_witness
            and mutations_complete
            and self.counterfactual_results
            and all(self.closure_checks.values())
        )
        if self.status != ("passed" if expected_passed else "blocked"):
            raise ValueError("mechanism necessity status is inconsistent")
        if bool(self.failure_reasons) == expected_passed:
            raise ValueError("mechanism necessity failure reasons are inconsistent")
        if self.artifact_id != mechanism_necessity_artifact_id(self):
            raise ValueError("mechanism necessity artifact identity is invalid")
        return self


class AlternativeValidPath(FrozenModel):
    path_id: str = Field(min_length=1)
    witness_id: str = Field(min_length=1)
    trajectory_hash: str = Field(min_length=1)
    model_owned_decision_signature: str = Field(min_length=1)
    behavior_signature: str = Field(min_length=1)
    quotient_state_id: str = Field(min_length=1)
    scaffold_surface_signature: str = Field(min_length=1)
    full_validity_passed: Literal[True] = True
    model_owned_decision: Literal[True] = True

    @model_validator(mode="after")
    def validate_path(self) -> AlternativeValidPath:
        if self.path_id != alternative_valid_path_id(self):
            raise ValueError("alternative valid path identity is invalid")
        return self


class AlternativeValidPathCatalog(FrozenModel):
    catalog_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    minimum_path_count: Literal[3] = 3
    paths: tuple[AlternativeValidPath, ...] = ()
    compiler_witness_count: int = Field(ge=0)
    scaffold_surface_only_path_count: int = Field(ge=0)
    status: Literal["passed", "blocked"]
    failure_reasons: tuple[str, ...]
    schema_version: str = EXECUTABLE_SUPPORT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_catalog(self) -> AlternativeValidPathCatalog:
        unique_path_ids = {item.path_id for item in self.paths}
        unique_decisions = {item.model_owned_decision_signature for item in self.paths}
        unique_behaviors = {item.behavior_signature for item in self.paths}
        unique_states = {item.quotient_state_id for item in self.paths}
        expected_passed = (
            len(self.paths) >= self.minimum_path_count
            and len(unique_path_ids) == len(self.paths)
            and len(unique_decisions) >= self.minimum_path_count
            and len(unique_behaviors) >= self.minimum_path_count
            and len(unique_states) >= self.minimum_path_count
            and self.scaffold_surface_only_path_count == 0
        )
        if self.status != ("passed" if expected_passed else "blocked"):
            raise ValueError("alternative valid path catalog status is inconsistent")
        if bool(self.failure_reasons) == expected_passed:
            raise ValueError("alternative path catalog failure reasons are inconsistent")
        if self.catalog_id != alternative_valid_path_catalog_id(self):
            raise ValueError("alternative valid path catalog identity is invalid")
        return self


class ExecutableSupportTaskCompilation(FrozenModel):
    compilation_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    source_mechanism_id: str = Field(min_length=1)
    target_mechanism_id: str = Field(min_length=1)
    answer_projection_contract_id: str = Field(min_length=1)
    public_witness_id: str = Field(min_length=1)
    mechanism_necessity_artifact_id: str = Field(min_length=1)
    alternative_path_catalog_id: str = Field(min_length=1)
    evidence_support_lattice_id: str = Field(min_length=1)
    answer_projection_bound: bool
    evidence_lattice_bound: bool
    public_witness_passed: bool
    mechanism_necessity_passed: bool
    alternative_paths_passed: bool
    capability_measurement_eligible: bool
    vtdo_multistate_eligible: bool
    assigned_task_use: TaskUse
    blockers: tuple[str, ...]
    schema_version: str = EXECUTABLE_SUPPORT_CONTRACT_VERSION

    @model_validator(mode="after")
    def validate_compilation(self) -> ExecutableSupportTaskCompilation:
        expected_capability = all(
            (
                self.answer_projection_bound,
                self.evidence_lattice_bound,
                self.public_witness_passed,
                self.mechanism_necessity_passed,
            )
        )
        expected_vtdo = expected_capability and self.alternative_paths_passed
        if self.capability_measurement_eligible != expected_capability:
            raise ValueError("capability-measurement eligibility is inconsistent")
        if self.vtdo_multistate_eligible != expected_vtdo:
            raise ValueError("VTDO multistate eligibility is inconsistent")
        expected_use: TaskUse = (
            "vtdo_multistate"
            if expected_vtdo
            else "capability_measurement"
            if expected_capability
            else "blocked"
        )
        if self.assigned_task_use != expected_use:
            raise ValueError("executable-support task use is inconsistent")
        blockers_required = expected_use != "vtdo_multistate"
        if bool(self.blockers) != blockers_required:
            raise ValueError("executable-support blockers are inconsistent")
        if self.compilation_id != executable_support_task_compilation_id(self):
            raise ValueError("executable-support task compilation identity is invalid")
        return self


def render_public_output_instruction(
    required_fields: tuple[str, ...],
    public_reference_labels: tuple[str, ...],
) -> str:
    fields = ", ".join(f"result.{item}" for item in required_fields)
    if public_reference_labels:
        labels = ", ".join(public_reference_labels)
        return f"Return exactly {fields}; any reference field must use one of: {labels}."
    return f"Return exactly {fields}."


def answer_projection_source_spec_hash(value: TypedAnswerProjectionContract) -> str:
    return canonical_hash(
        {
            "task_id": value.task_id,
            "source_task_hash": value.source_task_hash,
            "required_result_fields": value.required_result_fields,
            "allowed_result_fields": value.allowed_result_fields,
            "internal_reference_projection": value.internal_reference_projection,
            "public_reference_labels": value.public_reference_labels,
        },
        prefix="typed_answer_projection_source_spec:",
    )


def typed_answer_projection_contract_id(value: TypedAnswerProjectionContract) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"contract_id"}),
        prefix="typed_answer_projection_contract:",
    )


def evidence_support_set_id(value: EvidenceSupportSet) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"support_set_id"}),
        prefix="evidence_support_set:",
    )


def evidence_support_lattice_id(value: EvidenceSupportLattice) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"lattice_id"}),
        prefix="evidence_support_lattice:",
    )


def public_executable_witness_id(value: PublicExecutableWitnessArtifact) -> str:
    excluded = {"witness_id"}
    if value.schema_version == EXECUTABLE_SUPPORT_CONTRACT_VERSION_V1:
        excluded.update({"cited_evidence_ids", "citation_complete"})
    return canonical_hash(
        value.model_dump(mode="json", exclude=excluded),
        prefix="public_executable_witness:",
    )


def mechanism_counterfactual_result_id(value: MechanismCounterfactualResult) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"result_id"}),
        prefix="mechanism_counterfactual_result:",
    )


def mechanism_necessity_artifact_id(value: MechanismNecessityArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="mechanism_necessity_artifact:",
    )


def alternative_valid_path_id(value: AlternativeValidPath) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"path_id"}),
        prefix="alternative_valid_path:",
    )


def alternative_valid_path_catalog_id(value: AlternativeValidPathCatalog) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"catalog_id"}),
        prefix="alternative_valid_path_catalog:",
    )


def executable_support_task_compilation_id(
    value: ExecutableSupportTaskCompilation,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"compilation_id"}),
        prefix="executable_support_task_compilation:",
    )
