from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.executable_support import (
    MechanismNecessityArtifact,
)
from trusted_synthesis.core.trajectory.executable_task import (
    BoundPublicExecutableWitness,
    PublicRuntimeContract,
    StaticModelAuthorityPathCatalog,
    public_runtime_contract_id,
)
from trusted_synthesis.core.trajectory.public_operation import (
    AUTHORITY_PRESERVING_EXECUTABLE_TASK_PACKAGE_VERSION,
    AUTHORITY_PRESERVING_EXECUTABLE_VERIFIER_VERSION,
    AUTHORITY_PRESERVING_PUBLIC_OPERATION_CONTRACT_VERSION,
    AUTHORITY_PRESERVING_RUNTIME_PROJECTION_VERSION,
    AUTHORITY_PRESERVING_STOP_READINESS_VERSION,
    OperationalExecutableTaskPackage,
    OperationalExecutableVerifierBinding,
    PublicActionNeutralRepairContract,
    PublicOperationContractView,
    PublicOperationExecutionContract,
    PublicOperationRuntimeProjection,
    PublicStopReadinessContract,
    PublicTerminalVerificationTarget,
    PublicTerminalVerificationTargetView,
    operational_executable_task_package_id,
    operational_executable_verifier_binding_id,
    public_action_neutral_repair_contract_id,
    public_action_neutral_repair_view,
    public_operation_contract_view_id,
    public_operation_execution_contract_id,
    public_operation_runtime_projection_id,
    public_stop_readiness_contract_id,
    public_stop_readiness_view,
    public_terminal_verification_target_id,
    public_terminal_verification_target_view_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_executable_task_rematerialization import (  # noqa: E501
    MechanismCounterfactualReplayRecord,
    PathStrategy,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_rematerialization import (  # noqa: E501
    TARGET_MECHANISMS,
    ImmutableArtifactFile,
    ImplementationSourceFile,
    OperationalTaskAdmission,
    OperationalTaskRecord,
    OperationClosureAudit,
    PublicOperationRematerializationReport,
    operational_task_record_id,
)
from trusted_synthesis.experiments.vtdo_experiment.phase1_v26_public_operation_witness import (
    build_operation_closure_audit,
    build_operational_admission,
    compile_operational_witness,
    mechanism_necessity_and_catalog,
)
from trusted_synthesis.hashing import canonical_hash
from trusted_synthesis.runtime.agent.iterative import (
    AgentLoopPlanContract,
    _decision_prompt,
    _model_visible_environment,
)
from trusted_synthesis.runtime.agent.public_operation import (
    public_action_neutral_repair_context,
    public_action_neutral_repair_result,
    public_operation_progress,
    public_postcompletion_action_rejection,
    public_terminal_verification_rejection,
)
from trusted_synthesis.runtime.tools import (
    AgentToolCall,
    AgentToolEnvironmentManifest,
    AgentToolObservation,
    AgentToolResult,
    AgentToolSpec,
    make_agent_tool_environment_manifest,
    make_agent_tool_observation,
)

V26_AUTHORITY_PRESERVING_HARDENING_VERSION = (
    "finance_v26_authority_preserving_operation_hardening.v1"
)
V26_AUTHORITY_PRESERVING_TASK_AUDIT_VERSION = "finance_v26_authority_preserving_task_audit.v1"
V26_AUTHORITY_PRESERVING_LINEAGE_VERSION = "finance_v26_authority_preserving_contract_lineage.v1"
V26_AUTHORITY_PRESERVING_RUNTIME_ID = "finance.authority_preserving_executable_support_runtime"
V26_AUTHORITY_PRESERVING_RUNTIME_VERSION = (
    "finance_authority_preserving_executable_support_runtime.v1"
)
V26_AUTHORITY_PRESERVING_TOOLSET_VERSION = (
    "finance_authority_preserving_executable_support_toolset.v1"
)
V26_AUTHORITY_PRESERVING_VERIFIER_VERSION = "operational_executable_task_verifier.v3"
V26_AUTHORITY_PRESERVING_RECORD_VERSION = "finance_v26_public_operation_rematerialization.v3"

IMPLEMENTATION_SOURCE_PATHS = (
    "src/trusted_synthesis/core/trajectory/public_operation.py",
    "src/trusted_synthesis/domains/finance/executable_support_runtime.py",
    "src/trusted_synthesis/domains/finance/public_tool_results.py",
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_authority_preserving_operation_hardening.py"
    ),
    (
        "src/trusted_synthesis/experiments/vtdo_experiment/"
        "phase1_v26_public_operation_rematerialization.py"
    ),
    ("src/trusted_synthesis/experiments/vtdo_experiment/phase1_v26_public_operation_witness.py"),
    "src/trusted_synthesis/runtime/agent/iterative.py",
    "src/trusted_synthesis/runtime/agent/public_operation.py",
)

VerificationMutationKind = Literal[
    "missing_terminal_reference",
    "wrong_terminal_reference",
    "extra_terminal_claim_field",
    "verification_before_terminal",
    "postcompletion_action",
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SourceArtifactFile(FrozenModel):
    relative_path: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)
    record_count: int = Field(ge=1)


class TaskContractLineage(FrozenModel):
    lineage_id: str = Field(min_length=1)
    source_record_id: str = Field(min_length=1)
    hardened_record_id: str = Field(min_length=1)
    source_task_package_id: str = Field(min_length=1)
    hardened_task_package_id: str = Field(min_length=1)
    semantic_source_id: str = Field(min_length=1)
    semantic_source_unchanged: Literal[True] = True
    source_task_outcomes_used: Literal[False] = False
    operation_contract_identity_fresh: Literal[True] = True
    public_runtime_contract_identity_fresh: Literal[True] = True
    stop_readiness_contract_identity_fresh: Literal[True] = True
    action_neutral_repair_contract_created: Literal[True] = True
    terminal_verification_target_created: Literal[True] = True
    runtime_projection_identity_fresh: Literal[True] = True
    verifier_binding_identity_fresh: Literal[True] = True
    environment_manifest_identity_fresh: Literal[True] = True
    task_package_identity_fresh: Literal[True] = True
    schema_version: str = V26_AUTHORITY_PRESERVING_LINEAGE_VERSION

    @model_validator(mode="after")
    def validate_lineage(self) -> TaskContractLineage:
        if self.source_record_id == self.hardened_record_id:
            raise ValueError("authority-preserving record identity was reused")
        if self.source_task_package_id == self.hardened_task_package_id:
            raise ValueError("authority-preserving TaskPackage identity was reused")
        if self.lineage_id != task_contract_lineage_id(self):
            raise ValueError("authority-preserving lineage identity is invalid")
        return self


class ContractLineageAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=12)
    task_lineages: tuple[TaskContractLineage, ...] = Field(min_length=24, max_length=24)
    source_task_count: Literal[24] = 24
    hardened_task_count: Literal[24] = 24
    source_model_outcome_count: Literal[0] = 0
    source_model_outcomes_used: Literal[False] = False
    historical_artifacts_mutated: Literal[False] = False
    status: Literal["passed"] = "passed"
    schema_version: str = V26_AUTHORITY_PRESERVING_LINEAGE_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> ContractLineageAudit:
        if tuple(item.lineage_id for item in self.task_lineages) != tuple(
            sorted(item.lineage_id for item in self.task_lineages)
        ):
            raise ValueError("authority-preserving lineages are not canonical")
        if self.audit_id != contract_lineage_audit_id(self):
            raise ValueError("authority-preserving lineage audit identity is invalid")
        return self


class RepairPromptAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    repair_contract_id: str = Field(min_length=1)
    prompt_sha256: str = Field(min_length=64, max_length=64)
    exposed_context_fields: tuple[str, ...] = Field(min_length=1)
    failed_tool_id_exposed: Literal[True] = True
    typed_error_category_exposed: Literal[True] = True
    unresolved_semantics_exposed: Literal[True] = True
    unresolved_public_variables_exposed: Literal[True] = True
    correct_tool_disclosed: Literal[False] = False
    correct_operator_disclosed: Literal[False] = False
    correct_parameters_disclosed: Literal[False] = False
    expected_arguments_disclosed: Literal[False] = False
    action_binding_paths: tuple[str, ...] = ()
    raw_action_patch_removed: Literal[True] = True
    model_repair_authority_retained: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = V26_AUTHORITY_PRESERVING_TASK_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> RepairPromptAudit:
        if self.action_binding_paths:
            raise ValueError("repair Prompt retains an action-bearing field")
        if self.audit_id != repair_prompt_audit_id(self):
            raise ValueError("repair Prompt audit identity is invalid")
        return self


class VerificationMutationResult(FrozenModel):
    result_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mutation_kind: VerificationMutationKind
    expected_error_code: str = Field(min_length=1)
    observed_error_code: str = Field(min_length=1)
    failed_closed: Literal[True] = True
    schema_version: str = V26_AUTHORITY_PRESERVING_TASK_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_result(self) -> VerificationMutationResult:
        if self.expected_error_code != self.observed_error_code:
            raise ValueError("terminal verification mutation returned another error")
        if self.result_id != verification_mutation_result_id(self):
            raise ValueError("terminal verification mutation identity is invalid")
        return self


class AuthorityPreservingTaskAudit(FrozenModel):
    audit_id: str = Field(min_length=1)
    task_package_id: str = Field(min_length=1)
    mechanism_id: str = Field(min_length=1)
    repair_prompt_audit: RepairPromptAudit
    terminal_verification_target_id: str = Field(min_length=1)
    exact_terminal_reference_accepted: Literal[True] = True
    verification_mutations: tuple[VerificationMutationResult, ...] = Field(
        min_length=5, max_length=5
    )
    runtime_witness_stop_ready: Literal[True] = True
    mechanism_necessity_passed: Literal[True] = True
    operation_closure_passed: Literal[True] = True
    public_oracle_isolation_passed: Literal[True] = True
    status: Literal["passed"] = "passed"
    schema_version: str = V26_AUTHORITY_PRESERVING_TASK_AUDIT_VERSION

    @model_validator(mode="after")
    def validate_audit(self) -> AuthorityPreservingTaskAudit:
        expected = (
            "missing_terminal_reference",
            "wrong_terminal_reference",
            "extra_terminal_claim_field",
            "verification_before_terminal",
            "postcompletion_action",
        )
        if tuple(item.mutation_kind for item in self.verification_mutations) != expected:
            raise ValueError("terminal verification mutation matrix is incomplete")
        if self.repair_prompt_audit.task_package_id != self.task_package_id:
            raise ValueError("repair Prompt audit crosses TaskPackage identities")
        if self.audit_id != authority_preserving_task_audit_id(self):
            raise ValueError("authority-preserving task audit identity is invalid")
        return self


class AuthorityPreservingHardeningReport(FrozenModel):
    report_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    source_report_id: str = Field(min_length=1)
    source_report_sha256: str = Field(min_length=64, max_length=64)
    lineage_audit_id: str = Field(min_length=1)
    task_count: Literal[24] = 24
    mechanism_task_counts: dict[str, int]
    capability_task_count: Literal[12] = 12
    vtdo_candidate_task_count: Literal[12] = 12
    fresh_task_package_count: Literal[24] = 24
    fresh_public_runtime_contract_count: Literal[24] = 24
    action_neutral_repair_contract_count: Literal[24] = 24
    terminal_verification_target_count: Literal[24] = 24
    repair_prompt_audit_pass_count: Literal[24] = 24
    terminal_verification_audit_pass_count: Literal[24] = 24
    operation_closure_pass_count: Literal[24] = 24
    public_witness_pass_count: Literal[24] = 24
    compiler_generated_witness_count: Literal[48] = 48
    compiler_witness_pass_count: Literal[48] = 48
    mechanism_necessity_pass_count: Literal[24] = 24
    operational_capability_eligible_count: Literal[24] = 24
    operational_vtdo_candidate_eligible_count: Literal[12] = 12
    static_model_authority_path_count: Literal[36] = 36
    legacy_operation_mutation_count: int = Field(ge=192)
    authority_hardening_mutation_count: Literal[144] = 144
    task_records: tuple[OperationalTaskRecord, ...] = Field(min_length=24, max_length=24)
    admissions: tuple[OperationalTaskAdmission, ...] = Field(min_length=24, max_length=24)
    task_audits: tuple[AuthorityPreservingTaskAudit, ...] = Field(min_length=24, max_length=24)
    source_artifact_files: tuple[SourceArtifactFile, ...] = Field(min_length=12)
    immutable_artifact_files: tuple[ImmutableArtifactFile, ...] = Field(min_length=11)
    implementation_source_files: tuple[ImplementationSourceFile, ...] = Field(
        min_length=8, max_length=8
    )
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    historical_artifacts_mutated: Literal[False] = False
    status: Literal["passed"] = "passed"
    next_permitted_stage: Literal[
        "fresh_authority_preserving_instrument_requalification_protocol_only"
    ] = "fresh_authority_preserving_instrument_requalification_protocol_only"
    small_instrument_requalification_authorized: Literal[True] = True
    capability_development_authorized: Literal[False] = False
    state_reachability_pilot_authorized: Literal[False] = False
    fresh_confirmation_authorized: Literal[False] = False
    no_c_vtdo_authorized: Literal[False] = False
    student_training_authorized: Literal[False] = False
    exact_target_authorized: Literal[False] = False
    gp_c_authorized: Literal[False] = False
    production_contribution: Literal[0] = 0
    schema_version: str = V26_AUTHORITY_PRESERVING_HARDENING_VERSION

    @model_validator(mode="after")
    def validate_report(self) -> AuthorityPreservingHardeningReport:
        if self.mechanism_task_counts != {mechanism: 6 for mechanism in TARGET_MECHANISMS}:
            raise ValueError("authority-preserving mechanism quotas changed")
        groups = (
            tuple(item.record_id for item in self.task_records),
            tuple(item.admission_id for item in self.admissions),
            tuple(item.audit_id for item in self.task_audits),
        )
        if any(group != tuple(sorted(group)) for group in groups):
            raise ValueError("authority-preserving report details are not canonical")
        if tuple(item.relative_path for item in self.implementation_source_files) != tuple(
            sorted(IMPLEMENTATION_SOURCE_PATHS)
        ):
            raise ValueError("authority-preserving implementation manifest is incomplete")
        if self.report_id != authority_preserving_hardening_report_id(self):
            raise ValueError("authority-preserving hardening report identity is invalid")
        return self


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_count(path: Path) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 1


def _write_json(path: Path, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != serialized:
            raise ValueError(f"authority-preserving immutable JSON changed: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialized, encoding="utf-8")


def _write_models(path: Path, values: Sequence[BaseModel], identity: str) -> None:
    ordered = sorted(values, key=lambda item: str(getattr(item, identity)))
    _write_json(path, [item.model_dump(mode="json") for item in ordered])


def _artifact_file(path: Path, root: Path, count: int) -> ImmutableArtifactFile:
    return ImmutableArtifactFile(
        relative_path=path.relative_to(root).as_posix(),
        sha256=_sha256(path),
        record_count=count,
    )


def _implementation_source_files(package_root: Path) -> tuple[ImplementationSourceFile, ...]:
    return tuple(
        ImplementationSourceFile(
            relative_path=relative,
            sha256=_sha256(package_root / relative),
        )
        for relative in sorted(IMPLEMENTATION_SOURCE_PATHS)
    )


def _source_artifact_files(
    source_dir: Path,
    source_report: PublicOperationRematerializationReport,
) -> tuple[SourceArtifactFile, ...]:
    values = [
        SourceArtifactFile(
            relative_path="report.json",
            sha256=_sha256(source_dir / "report.json"),
            record_count=1,
        )
    ]
    for item in source_report.immutable_artifact_files:
        path = source_dir / item.relative_path
        if _sha256(path) != item.sha256 or _record_count(path) != item.record_count:
            raise ValueError(f"v26.65 source Artifact changed: {item.relative_path}")
        values.append(
            SourceArtifactFile(
                relative_path=item.relative_path,
                sha256=item.sha256,
                record_count=item.record_count,
            )
        )
    return tuple(sorted(values, key=lambda item: item.relative_path))


def _harden_environment(
    source: AgentToolEnvironmentManifest,
) -> AgentToolEnvironmentManifest:
    tools: list[AgentToolSpec] = []
    for item in source.tools:
        update: dict[str, Any] = {"tool_version": V26_AUTHORITY_PRESERVING_TOOLSET_VERSION}
        if item.tool_id == "cross_check_evidence":
            input_contract = dict(item.input_contract)
            input_contract["claim_or_result"] = (
                "object exactly {operation_ref: terminal_operation_ref}; additional claim "
                "fields are forbidden by the task PublicTerminalVerificationTarget"
            )
            update.update(
                {
                    "description": (
                        "Cross-check selected Evidence against the task's typed public terminal "
                        "verification target. After terminal completion, claim_or_result must "
                        "contain exactly the observed terminal operation_ref."
                    ),
                    "input_contract": input_contract,
                }
            )
        tools.append(item.model_copy(update=update))
    return make_agent_tool_environment_manifest(
        environment_id=f"{source.environment_id}.authority_preserving_v1",
        corpus_id=source.corpus_id,
        corpus_hash=source.corpus_hash,
        snapshot_id=source.snapshot_id,
        snapshot_hash=source.snapshot_hash,
        network_policy=source.network_policy,
        tools=tuple(tools),
        maximum_tool_calls=source.maximum_tool_calls,
        maximum_failed_tool_calls=source.maximum_failed_tool_calls,
        maximum_total_observation_bytes=source.maximum_total_observation_bytes,
        tool_timeout_seconds=source.tool_timeout_seconds,
    )


def _harden_record(
    source: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
) -> OperationalTaskRecord:
    base = source.task_package
    view_values = base.operation_contract.public_view.model_dump(mode="python", exclude={"view_id"})
    view_values["schema_version"] = AUTHORITY_PRESERVING_PUBLIC_OPERATION_CONTRACT_VERSION
    view_provisional = base.operation_contract.public_view.model_copy(
        update={
            "view_id": "pending",
            "schema_version": AUTHORITY_PRESERVING_PUBLIC_OPERATION_CONTRACT_VERSION,
        }
    )
    operation_view = PublicOperationContractView(
        view_id=public_operation_contract_view_id(view_provisional),
        **view_values,
    )
    operation_values = {
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "source_program_dag_hash": base.operation_contract.source_program_dag_hash,
        "source_verifier_dag_hash": base.operation_contract.source_verifier_dag_hash,
        "public_view": operation_view,
        "public_view_hash": canonical_hash(
            operation_view, prefix="public_operation_contract_view:"
        ),
        "schema_version": AUTHORITY_PRESERVING_PUBLIC_OPERATION_CONTRACT_VERSION,
    }
    operation_provisional = PublicOperationExecutionContract.model_construct(
        contract_id="pending", **operation_values
    )
    operation = PublicOperationExecutionContract(
        contract_id=public_operation_execution_contract_id(operation_provisional),
        **operation_values,
    )

    repair_values = {
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "operation_contract_id": operation.contract_id,
    }
    repair_provisional = PublicActionNeutralRepairContract.model_construct(
        contract_id="pending", **repair_values
    )
    repair = PublicActionNeutralRepairContract(
        contract_id=public_action_neutral_repair_contract_id(repair_provisional),
        **repair_values,
    )

    target_view_values = {"operation_contract_id": operation.contract_id}
    target_view_provisional = PublicTerminalVerificationTargetView.model_construct(
        view_id="pending", **target_view_values
    )
    target_view = PublicTerminalVerificationTargetView(
        view_id=public_terminal_verification_target_view_id(target_view_provisional),
        **target_view_values,
    )
    target_values = {
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "operation_contract_id": operation.contract_id,
        "source_verifier_dag_hash": operation.source_verifier_dag_hash,
        "public_view": target_view,
        "public_view_hash": canonical_hash(
            target_view, prefix="public_terminal_verification_target_view:"
        ),
    }
    target_provisional = PublicTerminalVerificationTarget.model_construct(
        target_id="pending", **target_values
    )
    target = PublicTerminalVerificationTarget(
        target_id=public_terminal_verification_target_id(target_provisional),
        **target_values,
    )

    stop_values = {
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "operation_contract_id": operation.contract_id,
        "required_node_ids": tuple(sorted(item.node_id for item in operation.public_view.nodes)),
        "terminal_node_id": operation.public_view.terminal_node_id,
        "terminal_verification_target_id": target.target_id,
        "schema_version": AUTHORITY_PRESERVING_STOP_READINESS_VERSION,
    }
    stop_provisional = PublicStopReadinessContract.model_construct(
        contract_id="pending", **stop_values
    )
    stop = PublicStopReadinessContract(
        contract_id=public_stop_readiness_contract_id(stop_provisional),
        **stop_values,
    )

    environment_hash = canonical_hash(environment, prefix="finance_v26_executable_environment:")
    runtime_values = {
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "tool_closure_contract_id": base.tool_closure.closure_id,
        "environment_manifest_hash": environment_hash,
        "runtime_implementation_id": V26_AUTHORITY_PRESERVING_RUNTIME_ID,
        "runtime_version": V26_AUTHORITY_PRESERVING_RUNTIME_VERSION,
        "allowed_tool_ids": base.tool_closure.allowed_tool_ids,
        "maximum_tool_calls": environment.maximum_tool_calls,
        "maximum_failed_tool_calls": environment.maximum_failed_tool_calls,
        "schema_version": base.public_runtime_contract.schema_version,
    }
    runtime_provisional = PublicRuntimeContract.model_construct(
        contract_id="pending", **runtime_values
    )
    runtime = PublicRuntimeContract(
        contract_id=public_runtime_contract_id(runtime_provisional),
        **runtime_values,
    )

    projection_values = {
        "operation_contract_id": operation.contract_id,
        "stop_readiness_contract_id": stop.contract_id,
        "action_neutral_repair_contract_id": repair.contract_id,
        "terminal_verification_target_id": target.target_id,
        "visible_progress_fields": tuple(
            sorted(
                {
                    *base.runtime_projection.visible_progress_fields,
                    "terminal_verification_target",
                }
            )
        ),
        "hidden_binding_fields": base.runtime_projection.hidden_binding_fields,
        "schema_version": AUTHORITY_PRESERVING_RUNTIME_PROJECTION_VERSION,
    }
    projection_provisional = PublicOperationRuntimeProjection.model_construct(
        projection_id="pending", **projection_values
    )
    projection = PublicOperationRuntimeProjection(
        projection_id=public_operation_runtime_projection_id(projection_provisional),
        **projection_values,
    )

    verifier_values = {
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "answer_projection_contract_id": base.answer_projection.contract_id,
        "evidence_support_lattice_id": base.evidence_support_lattice.lattice_id,
        "citation_contract_id": base.citation_contract.contract_id,
        "public_runtime_contract_id": runtime.contract_id,
        "mechanism_contract_id": base.mechanism_contract.contract_id,
        "operation_contract_id": operation.contract_id,
        "stop_readiness_contract_id": stop.contract_id,
        "runtime_projection_id": projection.projection_id,
        "action_neutral_repair_contract_id": repair.contract_id,
        "terminal_verification_target_id": target.target_id,
        "source_program_dag_hash": operation.source_program_dag_hash,
        "source_verifier_dag_hash": operation.source_verifier_dag_hash,
        "node_bindings": base.verifier_binding.node_bindings,
        "verifier_implementation_id": base.verifier_binding.verifier_implementation_id,
        "verifier_version": V26_AUTHORITY_PRESERVING_VERIFIER_VERSION,
        "exact_gold_equality_required": (base.verifier_binding.exact_gold_equality_required),
        "schema_version": AUTHORITY_PRESERVING_EXECUTABLE_VERIFIER_VERSION,
    }
    verifier_provisional = OperationalExecutableVerifierBinding.model_construct(
        binding_id="pending", **verifier_values
    )
    verifier = OperationalExecutableVerifierBinding(
        binding_id=operational_executable_verifier_binding_id(verifier_provisional),
        **verifier_values,
    )

    public_bindings = {
        "action_neutral_repair_contract_id": repair.contract_id,
        "answer_projection_contract_id": base.answer_projection.contract_id,
        "citation_contract_id": base.citation_contract.contract_id,
        "intended_use": base.semantic_source.intended_use,
        "operation_contract_id": operation.contract_id,
        "public_runtime_contract_id": runtime.contract_id,
        "runtime_projection_id": projection.projection_id,
        "stop_readiness_contract_id": stop.contract_id,
        "terminal_verification_target_id": target.target_id,
        "tool_closure_contract_id": base.tool_closure.closure_id,
    }
    oracle_bindings = {
        **public_bindings,
        "evidence_support_lattice_id": base.evidence_support_lattice.lattice_id,
        "mechanism_contract_id": base.mechanism_contract.contract_id,
        "semantic_source_id": base.semantic_source.semantic_source_id,
        "verifier_binding_id": verifier.binding_id,
    }
    source_guidance = base.task.public.metadata["agent_contract_guidance"]
    metadata = dict(base.task.public.metadata)
    metadata["executable_support_bindings"] = public_bindings
    metadata["agent_contract_guidance"] = {
        "public_operation_execution_contract": operation.public_view.model_dump(mode="json"),
        "public_stop_readiness_contract": public_stop_readiness_view(stop).model_dump(mode="json"),
        "public_action_neutral_repair_contract": public_action_neutral_repair_view(
            repair
        ).model_dump(mode="json"),
        "public_terminal_verification_target": target.public_view.model_dump(mode="json"),
        "answer_observation_constraints": source_guidance["answer_observation_constraints"],
    }
    public_template = base.task.public.model_copy(
        update={"task_id": "pending", "metadata": metadata}
    )
    selection_contract = dict(base.task.oracle.selection_contract)
    selection_contract["executable_support_bindings"] = oracle_bindings
    oracle_template = base.task.oracle.model_copy(
        update={"task_id": "pending", "selection_contract": selection_contract}
    )
    task_template = TaskPackage(
        task_id="pending",
        public=public_template,
        oracle=oracle_template,
    )
    package_values = {
        "semantic_source": base.semantic_source,
        "task": task_template,
        "tool_closure": base.tool_closure,
        "answer_projection": base.answer_projection,
        "evidence_support_lattice": base.evidence_support_lattice,
        "citation_contract": base.citation_contract,
        "public_runtime_contract": runtime,
        "mechanism_contract": base.mechanism_contract,
        "operation_contract": operation,
        "stop_readiness_contract": stop,
        "runtime_projection": projection,
        "verifier_binding": verifier,
        "action_neutral_repair_contract": repair,
        "terminal_verification_target": target,
        "schema_version": AUTHORITY_PRESERVING_EXECUTABLE_TASK_PACKAGE_VERSION,
    }
    package_provisional = OperationalExecutableTaskPackage.model_construct(
        package_id="pending", **package_values
    )
    package_id = operational_executable_task_package_id(package_provisional)
    task = TaskPackage(
        task_id=package_id,
        public=public_template.model_copy(update={"task_id": package_id}),
        oracle=oracle_template.model_copy(update={"task_id": package_id}),
    )
    package = OperationalExecutableTaskPackage(
        package_id=package_id,
        **{**package_values, "task": task},
    )
    record_values = {
        "mechanism_id": source.mechanism_id,
        "intended_use": source.intended_use,
        "source_task_artifact_ids": source.source_task_artifact_ids,
        "task_package": package,
        "evidence_bundle": source.evidence_bundle,
        "public_corpus": source.public_corpus,
        "proof_graph": source.proof_graph,
        "projected_expected_output": source.projected_expected_output,
        "answer_projection": source.answer_projection,
        "mechanism_public_state": source.mechanism_public_state,
        "mechanism_private_state": source.mechanism_private_state,
        "recovery_scenario": source.recovery_scenario,
        "target_program_evidence_ids": source.target_program_evidence_ids,
        "environment_manifest_id": environment.manifest_id,
        "environment_manifest_hash": environment_hash,
        "schema_version": V26_AUTHORITY_PRESERVING_RECORD_VERSION,
    }
    record_provisional = OperationalTaskRecord.model_construct(record_id="pending", **record_values)
    return OperationalTaskRecord(
        record_id=operational_task_record_id(record_provisional),
        **record_values,
    )


def _action_binding_paths(value: Any, forbidden: set[str], path: str) -> tuple[str, ...]:
    output: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            child = f"{path}.{key}"
            if key in forbidden:
                output.append(child)
            output.extend(_action_binding_paths(item, forbidden, child))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            output.extend(_action_binding_paths(item, forbidden, f"{path}[{index}]"))
    return tuple(output)


def _prompt_context(prompt: str) -> Mapping[str, Any]:
    marker = "\nPUBLIC_CONTEXT_JSON:\n"
    _, found, remainder = prompt.partition(marker)
    if not found:
        raise ValueError("authority-preserving audit Prompt lacks public Context")
    context_text, _, _ = remainder.partition("\nCONTRACT_REPAIR_JSON:\n")
    value = json.loads(context_text)
    if not isinstance(value, Mapping):
        raise ValueError("authority-preserving Prompt Context is malformed")
    return value


def _repair_prompt_audit(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    history: tuple[AgentToolObservation, ...],
) -> RepairPromptAudit:
    task = record.task_package.task.public
    operation_index = next(
        index
        for index, item in enumerate(history)
        if item.call.tool_id in {"calculator", "normalize_metric_unit_period"}
    )
    expected = history[operation_index].call
    prefix = history[:operation_index]
    failed_call = AgentToolCall(
        call_index=len(prefix) + 1,
        tool_id=expected.tool_id,
        arguments={},
    )
    raw_failure = AgentToolResult(
        status="failed",
        result={
            "retry_contract": {
                "policy": "destructive_action_binding_injection",
                "suggested_argument_patch": expected.arguments,
                "required_next_tools": (expected.tool_id,),
            }
        },
        error_code="destructive_action_binding_injection",
        error_message="synthetic static mutation",
    )
    sanitized = public_action_neutral_repair_result(task, prefix, failed_call, raw_failure)
    failed_observation = make_agent_tool_observation(
        environment_manifest_id=environment.manifest_id,
        call=failed_call,
        result=sanitized,
        observation_time_hash=canonical_hash(
            {
                "task_package_id": record.task_package.package_id,
                "mutation": "action_bearing_repair_injection",
            },
            prefix="finance_v26_authority_repair_mutation_time:",
        ),
    )
    mutated_history = (*prefix, failed_observation)
    prompt = _decision_prompt(
        task,
        _model_visible_environment(environment, consumed_tool_calls=len(mutated_history)),
        AgentLoopPlanContract(
            plan_summary="Resolve public semantics, execute, verify, and stop.",
            subgoal_labels=("resolve", "execute", "verify"),
            stop_conditions=("public stop readiness is true",),
        ),
        mutated_history,
        mode="autonomous_agent",
        expected_tool=None,
        public_state_condition=None,
        public_scaffold_context=None,
        host_feedback=(),
        observation_view="full",
    )
    context = _prompt_context(prompt)
    repair_context = context.get("failed_action_repair")
    if not isinstance(repair_context, Mapping):
        raise ValueError("authority-preserving Prompt lacks failed-action repair Context")
    observed = public_action_neutral_repair_context(task, mutated_history)
    normalized_observed = json.loads(json.dumps(observed, ensure_ascii=False, sort_keys=True))
    if repair_context != normalized_observed:
        raise ValueError("Prompt repair Context differs from Runtime projection")
    repair = record.task_package.action_neutral_repair_contract
    if repair is None:
        raise ValueError("authority-preserving TaskPackage lacks repair contract")
    forbidden = set(repair.forbidden_action_binding_fields)
    paths = tuple(
        sorted(
            {
                *_action_binding_paths(repair_context, forbidden, "failed_action_repair"),
                *_action_binding_paths(
                    failed_observation.result,
                    forbidden,
                    "latest_failed_observation.result",
                ),
            }
        )
    )
    values = {
        "task_package_id": record.task_package.package_id,
        "repair_contract_id": repair.contract_id,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "exposed_context_fields": tuple(sorted(repair_context)),
        "action_binding_paths": paths,
        "raw_action_patch_removed": "suggested_argument_patch"
        not in json.dumps(
            {
                "repair": repair_context,
                "result": failed_observation.result,
            },
            sort_keys=True,
        ),
    }
    provisional = RepairPromptAudit.model_construct(audit_id="pending", **values)
    return RepairPromptAudit(
        audit_id=repair_prompt_audit_id(provisional),
        **values,
    )


def _mutation_result(
    record: OperationalTaskRecord,
    kind: VerificationMutationKind,
    result: AgentToolResult,
    expected_error: str,
) -> VerificationMutationResult:
    values = {
        "task_package_id": record.task_package.package_id,
        "mutation_kind": kind,
        "expected_error_code": expected_error,
        "observed_error_code": result.error_code or "missing",
        "failed_closed": result.status == "failed",
    }
    provisional = VerificationMutationResult.model_construct(result_id="pending", **values)
    return VerificationMutationResult(
        result_id=verification_mutation_result_id(provisional),
        **values,
    )


def _verification_mutations(
    record: OperationalTaskRecord,
    history: tuple[AgentToolObservation, ...],
) -> tuple[bool, tuple[VerificationMutationResult, ...]]:
    task = record.task_package.task.public
    verification = next(item for item in history if item.call.tool_id == "cross_check_evidence")
    without_verification = tuple(
        item for item in history if item.observation_id != verification.observation_id
    )
    terminal_prefix_length = next(
        index
        for index in range(1, len(without_verification) + 1)
        if (progress := public_operation_progress(task, without_verification[:index])) is not None
        and progress["terminal_node_completed"]
    )
    preterminal = without_verification[: terminal_prefix_length - 1]
    terminal_history = without_verification[:terminal_prefix_length]
    exact = public_terminal_verification_rejection(task, terminal_history, verification.call)
    claim = verification.call.arguments["claim_or_result"]
    terminal_ref = claim["operation_ref"]
    evidence_ids = verification.call.arguments["evidence_ids"]

    def call(claim_value: dict[str, Any], index: int) -> AgentToolCall:
        return AgentToolCall(
            call_index=index,
            tool_id="cross_check_evidence",
            arguments={
                "evidence_ids": evidence_ids,
                "claim_or_result": claim_value,
            },
        )

    cases: list[
        tuple[
            VerificationMutationKind,
            tuple[AgentToolObservation, ...],
            AgentToolCall,
            str,
        ]
    ] = [
        (
            "missing_terminal_reference",
            terminal_history,
            call({}, len(terminal_history) + 1),
            "terminal_verification_reference_missing",
        ),
        (
            "wrong_terminal_reference",
            terminal_history,
            call(
                {"operation_ref": "operation:wrong_public_terminal_reference"},
                len(terminal_history) + 1,
            ),
            "terminal_verification_reference_wrong",
        ),
        (
            "extra_terminal_claim_field",
            terminal_history,
            call(
                {"operation_ref": terminal_ref, "value": "unregistered_extra"},
                len(terminal_history) + 1,
            ),
            "terminal_verification_extra_claim_fields",
        ),
        (
            "verification_before_terminal",
            preterminal,
            call({"operation_ref": terminal_ref}, len(preterminal) + 1),
            "terminal_verification_before_terminal",
        ),
    ]
    results = []
    for kind, prefix, mutation_call, expected in cases:
        rejection = public_terminal_verification_rejection(task, prefix, mutation_call)
        if rejection is None:
            raise ValueError(f"terminal verification mutation passed: {kind}")
        results.append(_mutation_result(record, kind, rejection, expected))

    extra_source = next(item for item in history if item.call.tool_id == "query_structured_fact")
    post_call = extra_source.call.model_copy(update={"call_index": len(history) + 1})
    post_rejection = public_postcompletion_action_rejection(task, history, post_call)
    if post_rejection is None:
        raise ValueError("postcompletion action mutation passed")
    results.append(
        _mutation_result(
            record,
            "postcompletion_action",
            post_rejection,
            "redundant_action_after_public_operation_completion",
        )
    )
    return exact is None, tuple(results)


def _task_audit(
    record: OperationalTaskRecord,
    environment: AgentToolEnvironmentManifest,
    witness: BoundPublicExecutableWitness,
    history: tuple[AgentToolObservation, ...],
    necessity: MechanismNecessityArtifact,
    closure: OperationClosureAudit,
) -> AuthorityPreservingTaskAudit:
    repair_audit = _repair_prompt_audit(record, environment, history)
    exact_accepted, mutations = _verification_mutations(record, history)
    target = record.task_package.terminal_verification_target
    if target is None:
        raise ValueError("authority-preserving TaskPackage lacks verification target")
    values = {
        "task_package_id": record.task_package.package_id,
        "mechanism_id": record.mechanism_id,
        "repair_prompt_audit": repair_audit,
        "terminal_verification_target_id": target.target_id,
        "exact_terminal_reference_accepted": exact_accepted,
        "verification_mutations": mutations,
        "runtime_witness_stop_ready": witness.full_validity_passed,
        "mechanism_necessity_passed": necessity.status == "passed",
        "operation_closure_passed": closure.status == "passed",
        "public_oracle_isolation_passed": closure.public_oracle_isolation_passed,
    }
    provisional = AuthorityPreservingTaskAudit.model_construct(audit_id="pending", **values)
    return AuthorityPreservingTaskAudit(
        audit_id=authority_preserving_task_audit_id(provisional),
        **values,
    )


def _lineage(
    source: OperationalTaskRecord,
    hardened: OperationalTaskRecord,
) -> TaskContractLineage:
    old = source.task_package
    new = hardened.task_package
    values = {
        "source_record_id": source.record_id,
        "hardened_record_id": hardened.record_id,
        "source_task_package_id": old.package_id,
        "hardened_task_package_id": new.package_id,
        "semantic_source_id": old.semantic_source.semantic_source_id,
        "semantic_source_unchanged": (
            old.semantic_source.semantic_source_id == new.semantic_source.semantic_source_id
        ),
        "operation_contract_identity_fresh": (
            old.operation_contract.contract_id != new.operation_contract.contract_id
        ),
        "public_runtime_contract_identity_fresh": (
            old.public_runtime_contract.contract_id != new.public_runtime_contract.contract_id
        ),
        "stop_readiness_contract_identity_fresh": (
            old.stop_readiness_contract.contract_id != new.stop_readiness_contract.contract_id
        ),
        "action_neutral_repair_contract_created": (new.action_neutral_repair_contract is not None),
        "terminal_verification_target_created": (new.terminal_verification_target is not None),
        "runtime_projection_identity_fresh": (
            old.runtime_projection.projection_id != new.runtime_projection.projection_id
        ),
        "verifier_binding_identity_fresh": (
            old.verifier_binding.binding_id != new.verifier_binding.binding_id
        ),
        "environment_manifest_identity_fresh": (
            source.environment_manifest_id != hardened.environment_manifest_id
        ),
        "task_package_identity_fresh": old.package_id != new.package_id,
    }
    provisional = TaskContractLineage.model_construct(lineage_id="pending", **values)
    return TaskContractLineage(
        lineage_id=task_contract_lineage_id(provisional),
        **values,
    )


def build_authority_preserving_operation_hardening(
    *,
    run_id: str,
    source_dir: Path,
    output_dir: Path,
    package_root: Path,
) -> AuthorityPreservingHardeningReport:
    source_report_path = source_dir / "report.json"
    source_report = PublicOperationRematerializationReport.model_validate_json(
        source_report_path.read_text(encoding="utf-8")
    )
    if source_report.status != "passed":
        raise ValueError("v26.65 source static Population is not passing")
    source_files = _source_artifact_files(source_dir, source_report)
    source_records = tuple(
        OperationalTaskRecord.model_validate(item)
        for item in json.loads(
            (source_dir / "operational_task_records.json").read_text(encoding="utf-8")
        )
    )
    source_environments = tuple(
        AgentToolEnvironmentManifest.model_validate(item)
        for item in json.loads(
            (source_dir / "tool_environment_manifests.json").read_text(encoding="utf-8")
        )
    )
    source_environment_by_id = {item.manifest_id: item for item in source_environments}
    records: list[OperationalTaskRecord] = []
    environments: list[AgentToolEnvironmentManifest] = []
    lineages: list[TaskContractLineage] = []
    for source in source_records:
        environment = _harden_environment(source_environment_by_id[source.environment_manifest_id])
        record = _harden_record(source, environment)
        records.append(record)
        environments.append(environment)
        lineages.append(_lineage(source, record))
    records.sort(key=lambda item: item.record_id)
    environments.sort(key=lambda item: item.manifest_id)
    lineages.sort(key=lambda item: item.lineage_id)
    if len({item.task_package.package_id for item in records}) != 24:
        raise ValueError("v26.65 produced duplicate TaskPackage identities")

    witnesses: list[BoundPublicExecutableWitness] = []
    observations: list[AgentToolObservation] = []
    necessities: list[MechanismNecessityArtifact] = []
    counterfactuals: list[MechanismCounterfactualReplayRecord] = []
    catalogs: list[StaticModelAuthorityPathCatalog] = []
    closures: list[OperationClosureAudit] = []
    admissions: list[OperationalTaskAdmission] = []
    audits: list[AuthorityPreservingTaskAudit] = []
    environment_by_id = {item.manifest_id: item for item in environments}
    for record in records:
        strategies: tuple[PathStrategy, ...] = (
            ("structured_direct",)
            if record.intended_use == "capability_measurement"
            else (
                "structured_direct",
                "search_then_structured",
                "search_then_open",
            )
        )
        task_witnesses = []
        task_histories = []
        for strategy in strategies:
            witness, history = compile_operational_witness(
                record,
                environment_by_id[record.environment_manifest_id],
                strategy=strategy,
            )
            task_witnesses.append(witness)
            task_histories.append(history)
            witnesses.append(witness)
            observations.extend(history)
        necessity, task_counterfactuals, catalog = mechanism_necessity_and_catalog(
            record, task_witnesses
        )
        closure = build_operation_closure_audit(
            record,
            task_witnesses,
            task_histories,
            necessity,
            catalog,
        )
        admission = build_operational_admission(
            record,
            task_witnesses[0],
            necessity,
            catalog,
            closure,
        )
        audit = _task_audit(
            record,
            environment_by_id[record.environment_manifest_id],
            task_witnesses[0],
            task_histories[0],
            necessity,
            closure,
        )
        necessities.append(necessity)
        counterfactuals.extend(task_counterfactuals)
        catalogs.append(catalog)
        closures.append(closure)
        admissions.append(admission)
        audits.append(audit)

    lineage_values = {
        "source_report_id": source_report.report_id,
        "source_report_sha256": _sha256(source_report_path),
        "source_artifact_files": source_files,
        "task_lineages": tuple(lineages),
    }
    lineage_provisional = ContractLineageAudit.model_construct(audit_id="pending", **lineage_values)
    lineage_audit = ContractLineageAudit(
        audit_id=contract_lineage_audit_id(lineage_provisional),
        **lineage_values,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "lineage": output_dir / "contract_lineage_audit.json",
        "records": output_dir / "operational_task_records.json",
        "environments": output_dir / "tool_environment_manifests.json",
        "witnesses": output_dir / "operational_public_witnesses.json",
        "observations": output_dir / "operational_witness_observations.json",
        "necessities": output_dir / "mechanism_necessity_artifacts.json",
        "counterfactuals": output_dir / "mechanism_counterfactual_replays.json",
        "catalogs": output_dir / "static_model_authority_path_catalogs.json",
        "closures": output_dir / "operation_closure_audits.json",
        "admissions": output_dir / "operational_task_admissions.json",
        "audits": output_dir / "authority_preserving_task_audits.json",
    }
    _write_json(paths["lineage"], lineage_audit.model_dump(mode="json"))
    _write_models(paths["records"], records, "record_id")
    _write_models(paths["environments"], environments, "manifest_id")
    _write_models(paths["witnesses"], witnesses, "witness_id")
    _write_models(paths["observations"], observations, "observation_id")
    _write_models(paths["necessities"], necessities, "artifact_id")
    _write_models(paths["counterfactuals"], counterfactuals, "replay_id")
    _write_models(paths["catalogs"], catalogs, "catalog_id")
    _write_models(paths["closures"], closures, "audit_id")
    _write_models(paths["admissions"], admissions, "admission_id")
    _write_models(paths["audits"], audits, "audit_id")
    counts = {
        "lineage": 1,
        "records": len(records),
        "environments": len(environments),
        "witnesses": len(witnesses),
        "observations": len(observations),
        "necessities": len(necessities),
        "counterfactuals": len(counterfactuals),
        "catalogs": len(catalogs),
        "closures": len(closures),
        "admissions": len(admissions),
        "audits": len(audits),
    }
    files = tuple(
        _artifact_file(path, output_dir, counts[key]) for key, path in sorted(paths.items())
    )
    values = {
        "run_id": run_id,
        "source_report_id": source_report.report_id,
        "source_report_sha256": _sha256(source_report_path),
        "lineage_audit_id": lineage_audit.audit_id,
        "mechanism_task_counts": {
            mechanism: sum(item.mechanism_id == mechanism for item in records)
            for mechanism in TARGET_MECHANISMS
        },
        "legacy_operation_mutation_count": sum(len(item.mutation_results) for item in closures),
        "task_records": tuple(sorted(records, key=lambda item: item.record_id)),
        "admissions": tuple(sorted(admissions, key=lambda item: item.admission_id)),
        "task_audits": tuple(sorted(audits, key=lambda item: item.audit_id)),
        "source_artifact_files": source_files,
        "immutable_artifact_files": files,
        "implementation_source_files": _implementation_source_files(package_root),
    }
    if Counter(item.mechanism_id for item in records) != Counter(
        {mechanism: 6 for mechanism in TARGET_MECHANISMS}
    ):
        raise ValueError("v26.65 mechanism quotas are incomplete")
    provisional = AuthorityPreservingHardeningReport.model_construct(report_id="pending", **values)
    report = AuthorityPreservingHardeningReport(
        report_id=authority_preserving_hardening_report_id(provisional),
        **values,
    )
    _write_json(output_dir / "report.json", report.model_dump(mode="json"))
    return report


def task_contract_lineage_id(value: TaskContractLineage) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"lineage_id"}),
        prefix="finance_v26_authority_preserving_task_lineage:",
    )


def contract_lineage_audit_id(value: ContractLineageAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_authority_preserving_lineage_audit:",
    )


def repair_prompt_audit_id(value: RepairPromptAudit) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_action_neutral_repair_prompt_audit:",
    )


def verification_mutation_result_id(value: VerificationMutationResult) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"result_id"}),
        prefix="finance_v26_terminal_verification_mutation:",
    )


def authority_preserving_task_audit_id(
    value: AuthorityPreservingTaskAudit,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"audit_id"}),
        prefix="finance_v26_authority_preserving_task_audit:",
    )


def authority_preserving_hardening_report_id(
    value: AuthorityPreservingHardeningReport,
) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"report_id"}),
        prefix="finance_v26_authority_preserving_hardening_report:",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the no-API Finance v26.65 authority-preserving Population"
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    report = build_authority_preserving_operation_hardening(
        run_id=args.run_id,
        source_dir=args.source_dir,
        output_dir=args.output_dir,
        package_root=args.package_root,
    )
    print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
