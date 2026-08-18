from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.trajectory.executable_task import (
    IntendedTaskUse,
)
from trusted_synthesis.core.trajectory.public_operation import (
    OperationalExecutableTaskPackage,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    TargetMechanism,
)
from trusted_synthesis.hashing import canonical_hash

V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION = "finance_v26_public_operation_rematerialization.v1"
V26_PUBLIC_OPERATION_COMPILER_VERSION = "finance_v26_public_operation_compiler.v1"
V26_OPERATION_CLOSURE_AUDIT_VERSION = "finance_v26_operation_closure_audit.v1"
V26_OPERATIONAL_VERIFIER_ID = "core.operational_executable_task_verifier"
V26_OPERATIONAL_VERIFIER_VERSION = "operational_executable_task_verifier.v1"

PATH_STRATEGIES = (
    "structured_direct",
    "search_then_structured",
    "search_then_open",
)
TARGET_MECHANISMS: tuple[TargetMechanism, ...] = (
    "context_conditioned_action",
    "semantic_reconciliation",
    "failure_recovery",
    "state_dependent_stopping",
)
MECHANISM_SOURCE_FAMILY = {
    "context_conditioned_action": "finance.branching_operation_plan",
    "failure_recovery": "finance.recovery_guided_search",
    "state_dependent_stopping": "finance.stopping_decision_control",
}
FRESHNESS_CHANNELS = (
    "source_task_artifact_id",
    "source_task_semantic_signature",
    "source_task_hash",
    "evidence_id",
    "evidence_version_id",
    "source_record_id",
)
IMPLEMENTATION_SOURCE_PATHS = (
    "src/trusted_synthesis/core/trajectory/public_operation.py",
    "src/trusted_synthesis/domains/finance/executable_support_runtime.py",
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_executable_task_rematerialization.py"
    ),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_public_operation_builder.py"),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_public_operation_pipeline.py"),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_public_operation_witness.py"),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_public_operation_rematerialization.py"
    ),
    "src/trusted_synthesis/runtime/agent/iterative.py",
    "src/trusted_synthesis/runtime/agent/public_operation.py",
)

PathStrategy = Literal[
    "structured_direct",
    "search_then_structured",
    "search_then_open",
]
OperationMutationKind = Literal[
    "required_node_ablation",
    "terminal_before_prerequisite",
    "first_calculation_only",
    "premature_verification",
    "terminal_missing",
    "postcompletion_action",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ImmutableArtifactFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class ImplementationSourceFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)


class FreshnessChannelAudit(FrozenModel):
    channel: str = Field(min_length=1)
    prior_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    prior_set_hash: str = Field(min_length=1)
    selected_set_hash: str = Field(min_length=1)
    overlap_values: tuple[str, ...] = ()
    overlap_count: Literal[0] = 0

    @model_validator(mode="after")
    def validate_channel(self) -> FreshnessChannelAudit:
        if self.channel not in FRESHNESS_CHANNELS:
            raise ValueError("freshness audit uses an unregistered channel")
        if self.overlap_values:
            raise ValueError("freshness channel contains prior identities")
        return self


class PublicOperationFreshnessAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    development_population_id: str = Field(min_length=1)
    prior_rematerialization_report_id: str = Field(min_length=1)
    source_population_ids: tuple[str, ...] = Field(min_length=3, max_length=3)
    tertiary_no_api_report_sha256: str = Field(min_length=64, max_length=64)
    tertiary_model_api_calls: Literal[0] = 0
    tertiary_gpu_jobs: Literal[0] = 0
    shared_read_only_source_container_ids: tuple[str, ...] = Field(min_length=1)
    source_container_reuse_policy: Literal[
        "immutable_container_shared_rows_must_be_identity_disjoint"
    ] = "immutable_container_shared_rows_must_be_identity_disjoint"
    selected_reconciliation_source_record_overlap_count: Literal[0] = 0
    channels: tuple[FreshnessChannelAudit, ...] = Field(min_length=6, max_length=6)
    selected_task_count: Literal[18] = 18
    selected_reconciliation_evidence_count: Literal[24] = 24
    status: Literal["passed"] = "passed"
    schema_version: str = V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> PublicOperationFreshnessAudit:
        if tuple(item.channel for item in self.channels) != tuple(sorted(FRESHNESS_CHANNELS)):
            raise ValueError("freshness channels are incomplete or noncanonical")
        if self.source_population_ids != tuple(sorted(set(self.source_population_ids))):
            raise ValueError("freshness source populations are not canonical")
        if self.shared_read_only_source_container_ids != tuple(
            sorted(set(self.shared_read_only_source_container_ids))
        ):
            raise ValueError("shared source containers are not canonical")
        if self.audit_id != public_operation_freshness_audit_id(self):
            raise ValueError("public Operation freshness identity is invalid")
        return self


class OperationalTaskRecord(FrozenModel):
    record_id: str = Field(min_length=1)
    mechanism_id: TargetMechanism
    intended_use: IntendedTaskUse
    source_task_artifact_ids: tuple[str, ...] = Field(min_length=1)
    task_package: OperationalExecutableTaskPackage
    evidence_bundle: EvidenceBundle
    public_corpus: EvidenceCorpus
    proof_graph: ProofGraph
    projected_expected_output: dict[str, Any]
    answer_projection: dict[str, str]
    mechanism_public_state: dict[str, Any]
    mechanism_private_state: dict[str, Any]
    recovery_scenario: dict[str, Any] | None = None
    target_program_evidence_ids: tuple[str, ...] = Field(min_length=1)
    environment_manifest_id: str = Field(min_length=1)
    environment_manifest_hash: str = Field(min_length=1)
    compiler_reference_policy: Literal["public_contract_only"] = "public_contract_only"
    compiler_witness_model_generated: Literal[False] = False
    schema_version: str = V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_record(self) -> OperationalTaskRecord:
        package = self.task_package
        if package.semantic_source.intended_use != self.intended_use:
            raise ValueError("operational task role differs from its semantic source")
        if package.mechanism_contract.target_mechanism_id != self.mechanism_id:
            raise ValueError("operational task mechanism differs from its contract")
        if package.semantic_source.evidence_bundle_hash != self.evidence_bundle.bundle_hash:
            raise ValueError("operational task Evidence Bundle changed")
        if package.semantic_source.public_corpus_hash != self.public_corpus.corpus_hash:
            raise ValueError("operational task Public Corpus changed")
        if package.semantic_source.proof_graph_hash != self.proof_graph.graph_hash:
            raise ValueError("operational task Proof Graph changed")
        if self.record_id != operational_task_record_id(self):
            raise ValueError("operational task record identity is invalid")
        return self


class OperationClosureMutationResult(FrozenModel):
    result_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    baseline_witness_id: str = Field(min_length=1)
    mutation_kind: OperationMutationKind
    removed_node_id: str | None = None
    runtime_rejection_error_code: str | None = None
    all_steps_completed: bool
    terminal_node_completed: bool
    verification_after_terminal_completed: bool
    postcompletion_violation: bool
    stop_ready: Literal[False] = False
    failure_closed: Literal[True] = True
    progress_hash: str = Field(min_length=1)
    schema_version: str = V26_OPERATION_CLOSURE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> OperationClosureMutationResult:
        if self.mutation_kind == "required_node_ablation" and self.removed_node_id is None:
            raise ValueError("node-ablation result lacks its removed node")
        if self.mutation_kind != "required_node_ablation" and self.removed_node_id is not None:
            raise ValueError("non-ablation mutation unexpectedly names a removed node")
        if self.result_id != operation_closure_mutation_result_id(self):
            raise ValueError("Operation-closure mutation result identity is invalid")
        return self


class OperationPathClosureResult(FrozenModel):
    result_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    path_strategy_id: PathStrategy
    witness_id: str = Field(min_length=1)
    all_steps_completed: Literal[True] = True
    terminal_node_completed: Literal[True] = True
    verification_after_terminal_completed: Literal[True] = True
    postcompletion_violation: Literal[False] = False
    stop_ready: Literal[True] = True
    normalized_answer_hash: str = Field(min_length=1)
    schema_version: str = V26_OPERATION_CLOSURE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> OperationPathClosureResult:
        if self.result_id != operation_path_closure_result_id(self):
            raise ValueError("Operation path-closure result identity is invalid")
        return self


class OperationClosureAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    intended_use: IntendedTaskUse
    operation_contract_id: str = Field(min_length=1)
    source_program_dag_hash: str = Field(min_length=1)
    source_verifier_dag_hash: str = Field(min_length=1)
    terminal_node_id: str = Field(min_length=1)
    stop_readiness_contract_id: str = Field(min_length=1)
    runtime_projection_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    mechanism_necessity_artifact_id: str = Field(min_length=1)
    required_node_ids: tuple[str, ...] = Field(min_length=1)
    path_results: tuple[OperationPathClosureResult, ...] = Field(min_length=1, max_length=3)
    mutation_results: tuple[OperationClosureMutationResult, ...] = Field(min_length=6)
    every_required_node_ablation_failed_closed: Literal[True] = True
    target_mechanism_counterfactual_failed_closed: Literal[True] = True
    public_oracle_isolation_passed: Literal[True] = True
    exact_tool_sequence_exposed: Literal[False] = False
    correct_model_choice_exposed: Literal[False] = False
    compiler_used_oracle_next_action: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_OPERATION_CLOSURE_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> OperationClosureAudit:
        expected_paths = (
            ("structured_direct",)
            if self.intended_use == "capability_measurement"
            else PATH_STRATEGIES
        )
        if tuple(item.path_strategy_id for item in self.path_results) != expected_paths:
            raise ValueError("Operation closure paths differ from the registered task role")
        if len({item.normalized_answer_hash for item in self.path_results}) != 1:
            raise ValueError("public acquisition paths do not reach one answer closure")
        ablations = tuple(
            item.removed_node_id
            for item in self.mutation_results
            if item.mutation_kind == "required_node_ablation"
        )
        if ablations != self.required_node_ids:
            raise ValueError("Operation closure did not ablate every required node")
        required_mutations = {
            "terminal_before_prerequisite",
            "first_calculation_only",
            "premature_verification",
            "terminal_missing",
            "postcompletion_action",
        }
        observed = {
            item.mutation_kind
            for item in self.mutation_results
            if item.mutation_kind != "required_node_ablation"
        }
        if observed != required_mutations:
            raise ValueError("Operation closure destructive mutation matrix is incomplete")
        if self.audit_id != operation_closure_audit_id(self):
            raise ValueError("Operation-closure audit identity is invalid")
        return self


class OperationalTaskAdmission(FrozenModel):
    admission_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    intended_use: IntendedTaskUse
    public_witness_id: str = Field(min_length=1)
    mechanism_necessity_artifact_id: str = Field(min_length=1)
    static_path_catalog_id: str = Field(min_length=1)
    operation_closure_audit_id: str = Field(min_length=1)
    package_bindings_passed: bool
    public_witness_passed: bool
    mechanism_necessity_passed: bool
    operation_closure_passed: bool
    static_path_support_passed: bool
    operational_capability_eligible: bool
    operational_vtdo_candidate_eligible: bool
    status: Literal["operational_capability_ready", "operational_vtdo_ready", "blocked"]
    blockers: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_admission(self) -> OperationalTaskAdmission:
        capability = (
            self.package_bindings_passed
            and self.public_witness_passed
            and self.mechanism_necessity_passed
            and self.operation_closure_passed
        )
        vtdo = (
            capability
            and self.intended_use == "vtdo_multistate_candidate"
            and self.static_path_support_passed
        )
        if self.operational_capability_eligible != capability:
            raise ValueError("operational capability admission is inconsistent")
        if self.operational_vtdo_candidate_eligible != vtdo:
            raise ValueError("operational VTDO admission is inconsistent")
        expected = (
            "operational_vtdo_ready"
            if vtdo
            else "operational_capability_ready"
            if capability and self.intended_use == "capability_measurement"
            else "blocked"
        )
        if self.status != expected:
            raise ValueError("operational task admission status is inconsistent")
        if self.admission_id != operational_task_admission_id(self):
            raise ValueError("operational task admission identity is invalid")
        return self


class PublicOperationRematerializationReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    development_population_id: str = Field(min_length=1)
    prior_rematerialization_report_id: str = Field(min_length=1)
    exposure_receipt_id: str = Field(min_length=1)
    definition_pair_capacity_audit_id: str = Field(min_length=1)
    freshness_audit_id: str = Field(min_length=1)
    task_count: Literal[24] = 24
    target_mechanism_task_counts: dict[TargetMechanism, int]
    intended_capability_task_count: Literal[12] = 12
    intended_vtdo_candidate_task_count: Literal[12] = 12
    public_operation_contract_count: int = Field(ge=0, le=24)
    operation_closure_pass_count: int = Field(ge=0, le=24)
    public_witness_pass_count: int = Field(ge=0, le=24)
    mechanism_necessity_pass_count: int = Field(ge=0, le=24)
    operational_capability_eligible_count: int = Field(ge=0, le=24)
    operational_vtdo_candidate_eligible_count: int = Field(ge=0, le=12)
    static_model_authority_path_count: int = Field(ge=0)
    destructive_mutation_count: int = Field(ge=1)
    compiler_generated_witness_count: Literal[48] = 48
    compiler_witness_pass_count: Literal[48] = 48
    model_generated_path_count: Literal[0] = 0
    task_records: tuple[OperationalTaskRecord, ...] = Field(min_length=24, max_length=24)
    admissions: tuple[OperationalTaskAdmission, ...] = Field(min_length=24, max_length=24)
    immutable_artifact_files: tuple[ImmutableArtifactFile, ...] = Field(min_length=10)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=9, max_length=9
    )
    status: Literal["passed", "blocked"]
    next_permitted_stage: Literal[
        "fresh_operation_closure_regression_protocol_only",
        "fresh_public_operation_contract_rematerialization_only",
    ]
    small_regression_protocol_authorized: bool
    capability_development_authorized: Literal[False] = False
    state_reachability_pilot_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = V26_PUBLIC_OPERATION_REMATERIALIZATION_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> PublicOperationRematerializationReport:
        if self.target_mechanism_task_counts != {mechanism: 6 for mechanism in TARGET_MECHANISMS}:
            raise ValueError("public Operation task mechanism quotas changed")
        if tuple(item.record_id for item in self.task_records) != tuple(
            sorted(item.record_id for item in self.task_records)
        ):
            raise ValueError("operational task records are not canonical")
        if tuple(item.admission_id for item in self.admissions) != tuple(
            sorted(item.admission_id for item in self.admissions)
        ):
            raise ValueError("operational admissions are not canonical")
        capability = sum(item.operational_capability_eligible for item in self.admissions)
        vtdo = sum(item.operational_vtdo_candidate_eligible for item in self.admissions)
        if capability != self.operational_capability_eligible_count:
            raise ValueError("report operational capability denominator is inconsistent")
        if vtdo != self.operational_vtdo_candidate_eligible_count:
            raise ValueError("report operational VTDO denominator is inconsistent")
        passed = (
            capability == 24
            and vtdo == 12
            and self.operation_closure_pass_count == 24
            and self.compiler_witness_pass_count == self.compiler_generated_witness_count
        )
        if self.status != ("passed" if passed else "blocked"):
            raise ValueError("public Operation rematerialization status is inconsistent")
        if self.small_regression_protocol_authorized != passed:
            raise ValueError("small regression authorization is inconsistent")
        expected_stage = (
            "fresh_operation_closure_regression_protocol_only"
            if passed
            else "fresh_public_operation_contract_rematerialization_only"
        )
        if self.next_permitted_stage != expected_stage:
            raise ValueError("public Operation transition is inconsistent")
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("public Operation implementation manifest is incomplete")
        if self.report_id != public_operation_rematerialization_report_id(self):
            raise ValueError("public Operation rematerialization report identity is invalid")
        return self


def public_operation_freshness_audit_id(
    value: PublicOperationFreshnessAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_public_operation_freshness_audit:",
    )


def operational_task_record_id(value: OperationalTaskRecord) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"record_id"}),
        prefix="finance_v26_operational_task_record:",
    )


def operation_closure_mutation_result_id(
    value: OperationClosureMutationResult,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"result_id"}),
        prefix="finance_v26_operation_closure_mutation:",
    )


def operation_path_closure_result_id(value: OperationPathClosureResult) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"result_id"}),
        prefix="finance_v26_operation_path_closure:",
    )


def operation_closure_audit_id(value: OperationClosureAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_operation_closure_audit:",
    )


def operational_task_admission_id(value: OperationalTaskAdmission) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"admission_id"}),
        prefix="finance_v26_operational_task_admission:",
    )


def public_operation_rematerialization_report_id(
    value: PublicOperationRematerializationReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_public_operation_rematerialization_report:",
    )
