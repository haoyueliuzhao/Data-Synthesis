from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.schema import ReleaseDecision
from trusted_synthesis.core.synthesis.schema import (
    CompiledProofCarryingArtifacts,
    ProofCarryingPublicArtifact,
)
from trusted_synthesis.core.synthesis.validation import validate_compiled_artifacts
from trusted_synthesis.core.trajectory.state import TRAJECTORY_CANONICALIZER_VERSION
from trusted_synthesis.core.vtdo.state_space import (
    PublicStateCondition,
    TrajectoryStateSpaceCompilation,
)
from trusted_synthesis.hashing import canonical_hash

JOINT_COMPILATION_ADMISSION_VERSION = "joint_compilation_admission.v1"
RUNTIME_PUBLIC_PROJECTION_VERSION = "joint_runtime_public_projection.v1"
JOINT_COMPILATION_AUDIT_EVIDENCE_VERSION = "joint_compilation_audit_evidence.v1"

AuditKind = Literal[
    "public_sufficiency",
    "executable_closure",
    "destructive_mutation",
]

PUBLIC_SUFFICIENCY_CHECKS: tuple[str, ...] = (
    "decision_information_present",
    "critical_state_ablation_changes_decidability",
    "oracle_fields_absent",
    "runtime_projection_from_joint_source",
)
EXECUTABLE_CLOSURE_CHECKS: tuple[str, ...] = (
    "action_preconditions_closed",
    "evidence_locators_reachable",
    "tool_order_replayable",
    "budget_feasible",
)
DESTRUCTIVE_MUTATION_CHECKS: tuple[str, ...] = (
    "remove_required_evidence_rejected",
    "mutate_program_node_rejected",
    "swap_operand_rejected",
    "change_time_or_unit_rejected",
    "break_proof_edge_rejected",
    "inject_host_only_field_rejected",
    "mutate_state_mapper_rejected",
    "replace_public_projection_rejected",
)
JOINT_COMPILATION_GATES: tuple[str, ...] = (
    "semantic_closure",
    "public_sufficiency",
    "executable_closure",
    "verifier_consistency",
    "recursive_noninterference",
    "state_and_lineage_closure",
    "destructive_mutation_rejection",
)


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RuntimePublicProjection(FrozenModel):
    projection_id: str = Field(min_length=1)
    runtime_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    omega_context_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    public_artifact: ProofCarryingPublicArtifact
    public_corpus_id: str = Field(min_length=1)
    public_corpus_hash: str = Field(min_length=1)
    state_space_compilation_id: str = Field(min_length=1)
    state_conditions: tuple[PublicStateCondition, ...] = Field(min_length=1)
    allowed_tools: tuple[str, ...] = Field(min_length=1)
    schema_version: str = RUNTIME_PUBLIC_PROJECTION_VERSION

    @model_validator(mode="after")
    def validate_projection(self) -> RuntimePublicProjection:
        if self.public_artifact.task_public.task_id != self.task_id:
            raise ValueError("runtime projection crosses task identities")
        if (
            self.public_artifact.public_corpus_id != self.public_corpus_id
            or self.public_artifact.public_corpus_hash != self.public_corpus_hash
        ):
            raise ValueError("runtime projection crosses public Corpus identities")
        if self.allowed_tools != tuple(sorted(self.public_artifact.task_public.allowed_tools)):
            raise ValueError("runtime projection tools differ from the public task")
        if any(condition.task_id != self.task_id for condition in self.state_conditions):
            raise ValueError("runtime projection contains a foreign state condition")
        if len({item.condition_id for item in self.state_conditions}) != len(self.state_conditions):
            raise ValueError("runtime projection contains duplicate state conditions")
        if self.projection_id != runtime_public_projection_id(self):
            raise ValueError("runtime public projection identity is invalid")
        return self


class JointCompilationAuditEvidence(FrozenModel):
    evidence_id: str = Field(min_length=1)
    audit_kind: AuditKind
    joint_compilation_id: str = Field(min_length=1)
    checks: dict[str, bool]
    passed: bool
    auditor_id: str = Field(min_length=1)
    auditor_version: str = Field(min_length=1)
    schema_version: str = JOINT_COMPILATION_AUDIT_EVIDENCE_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> JointCompilationAuditEvidence:
        expected = {
            "public_sufficiency": PUBLIC_SUFFICIENCY_CHECKS,
            "executable_closure": EXECUTABLE_CLOSURE_CHECKS,
            "destructive_mutation": DESTRUCTIVE_MUTATION_CHECKS,
        }[self.audit_kind]
        if tuple(sorted(self.checks)) != tuple(sorted(expected)):
            raise ValueError("Joint Compilation audit checks are incomplete")
        if self.passed != all(self.checks.values()):
            raise ValueError("Joint Compilation audit status is inconsistent")
        if self.evidence_id != joint_compilation_audit_evidence_id(self):
            raise ValueError("Joint Compilation audit Evidence identity is invalid")
        return self


class JointCompilationAdmissionArtifact(FrozenModel):
    admission_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    omega_context_id: str = Field(min_length=1)
    omega_component_manifest_id: str = Field(min_length=1)
    state_space_compilation_id: str = Field(min_length=1)
    runtime_projections: tuple[RuntimePublicProjection, ...] = Field(min_length=1)
    verifier_id: str = Field(min_length=1)
    verifier_version: str = Field(min_length=1)
    state_mapper_version: str = Field(min_length=1)
    materialization_contract_id: str = Field(min_length=1)
    materialization_contract_version: str = Field(min_length=1)
    public_sufficiency_evidence: JointCompilationAuditEvidence
    executable_closure_evidence: JointCompilationAuditEvidence
    destructive_mutation_evidence: JointCompilationAuditEvidence
    gates: dict[str, bool]
    status: Literal["admitted", "blocked"]
    blockers: tuple[str, ...]
    next_transition: Literal[
        "agent_state_discovery",
        "joint_compilation_repair_only",
    ]
    model_api_calls: Literal[0] = 0
    gpu_jobs: Literal[0] = 0
    schema_version: str = JOINT_COMPILATION_ADMISSION_VERSION

    @model_validator(mode="after")
    def validate_admission(self) -> JointCompilationAdmissionArtifact:
        if tuple(sorted(self.gates)) != tuple(sorted(JOINT_COMPILATION_GATES)):
            raise ValueError("Joint Compilation admission gates are incomplete")
        expected_status = "admitted" if all(self.gates.values()) else "blocked"
        if self.status != expected_status:
            raise ValueError("Joint Compilation admission status is inconsistent")
        expected_blockers = tuple(sorted(name for name, passed in self.gates.items() if not passed))
        if self.blockers != expected_blockers:
            raise ValueError("Joint Compilation admission blockers are inconsistent")
        expected_transition = (
            "agent_state_discovery"
            if self.status == "admitted"
            else "joint_compilation_repair_only"
        )
        if self.next_transition != expected_transition:
            raise ValueError("Joint Compilation admission transition is inconsistent")
        if len({item.runtime_id for item in self.runtime_projections}) != len(
            self.runtime_projections
        ):
            raise ValueError("Joint Compilation runtime projections are duplicated")
        if any(
            item.joint_compilation_id != self.joint_compilation_id
            or item.omega_context_id != self.omega_context_id
            or item.state_space_compilation_id != self.state_space_compilation_id
            for item in self.runtime_projections
        ):
            raise ValueError("Joint Compilation views do not share one semantic root")
        evidence = (
            self.public_sufficiency_evidence,
            self.executable_closure_evidence,
            self.destructive_mutation_evidence,
        )
        if any(item.joint_compilation_id != self.joint_compilation_id for item in evidence):
            raise ValueError("Joint Compilation audit Evidence belongs to another compilation")
        if self.admission_id != joint_compilation_admission_id(self):
            raise ValueError("Joint Compilation admission identity is invalid")
        return self


def make_runtime_public_projection(
    artifacts: CompiledProofCarryingArtifacts,
    state_space: TrajectoryStateSpaceCompilation,
    *,
    runtime_id: str,
) -> RuntimePublicProjection:
    joint = artifacts.joint_compilation
    if state_space.joint_compilation_artifact_id != joint.artifact_id:
        raise ValueError("runtime projection state space is detached from Joint Compilation")
    conditions = tuple(
        state_space.public_conditions_by_variation_id[key]
        for key in sorted(state_space.public_conditions_by_variation_id)
    )
    values = {
        "runtime_id": runtime_id,
        "joint_compilation_id": joint.artifact_id,
        "omega_context_id": joint.omega.context_id,
        "task_id": joint.omega.task.task_id,
        "public_artifact": artifacts.public_artifact,
        "public_corpus_id": joint.omega.public_corpus.corpus_id,
        "public_corpus_hash": joint.omega.public_corpus.corpus_hash,
        "state_space_compilation_id": state_space.compilation_id,
        "state_conditions": conditions,
        "allowed_tools": tuple(sorted(joint.omega.task.public.allowed_tools)),
        "schema_version": RUNTIME_PUBLIC_PROJECTION_VERSION,
    }
    provisional = RuntimePublicProjection.model_construct(projection_id="pending", **values)
    projection = RuntimePublicProjection(
        projection_id=runtime_public_projection_id(provisional),
        **values,
    )
    if _projection_leaks_oracle(projection, artifacts):
        raise ValueError("runtime projection leaks Oracle-only Joint Compilation fields")
    return projection


def make_joint_compilation_audit_evidence(
    *,
    audit_kind: AuditKind,
    joint_compilation_id: str,
    checks: Mapping[str, bool],
    auditor_id: str,
    auditor_version: str,
) -> JointCompilationAuditEvidence:
    values = {
        "audit_kind": audit_kind,
        "joint_compilation_id": joint_compilation_id,
        "checks": dict(sorted(checks.items())),
        "passed": all(checks.values()),
        "auditor_id": auditor_id,
        "auditor_version": auditor_version,
        "schema_version": JOINT_COMPILATION_AUDIT_EVIDENCE_VERSION,
    }
    provisional = JointCompilationAuditEvidence.model_construct(evidence_id="pending", **values)
    return JointCompilationAuditEvidence(
        evidence_id=joint_compilation_audit_evidence_id(provisional),
        **values,
    )


def admit_joint_compilation(
    artifacts: CompiledProofCarryingArtifacts,
    state_space: TrajectoryStateSpaceCompilation,
    *,
    runtime_projections: tuple[RuntimePublicProjection, ...],
    public_sufficiency_evidence: JointCompilationAuditEvidence,
    executable_closure_evidence: JointCompilationAuditEvidence,
    destructive_mutation_evidence: JointCompilationAuditEvidence,
    verifier_id: str,
    verifier_version: str,
    materialization_contract_id: str,
    materialization_contract_version: str,
) -> JointCompilationAdmissionArtifact:
    validate_compiled_artifacts(artifacts)
    joint = artifacts.joint_compilation
    semantic_closure = (
        artifacts.reference_assessment.decision == ReleaseDecision.ACCEPTED
        and not artifacts.reference_assessment.fatal_failures
        and not artifacts.reference_assessment.failed_check_ids
    )
    projection_ids_consistent = bool(runtime_projections) and all(
        item.joint_compilation_id == joint.artifact_id
        and item.omega_context_id == joint.omega.context_id
        and item.task_id == joint.omega.task.task_id
        and item.state_space_compilation_id == state_space.compilation_id
        and item.public_corpus_id == joint.omega.public_corpus.corpus_id
        and item.public_corpus_hash == joint.omega.public_corpus.corpus_hash
        for item in runtime_projections
    )
    state_lineage = (
        state_space.joint_compilation_artifact_id == joint.artifact_id
        and state_space.omega_context_id == joint.omega.context_id
        and state_space.omega_component_manifest == joint.component_manifest
        and bool(materialization_contract_id)
        and bool(materialization_contract_version)
    )
    noninterference = projection_ids_consistent and all(
        not _projection_leaks_oracle(item, artifacts) for item in runtime_projections
    )
    audits = {
        item.audit_kind: item
        for item in (
            public_sufficiency_evidence,
            executable_closure_evidence,
            destructive_mutation_evidence,
        )
    }
    audit_identity_consistent = len(audits) == 3 and all(
        item.joint_compilation_id == joint.artifact_id for item in audits.values()
    )
    gates = {
        "semantic_closure": semantic_closure,
        "public_sufficiency": (audit_identity_consistent and public_sufficiency_evidence.passed),
        "executable_closure": (
            semantic_closure and audit_identity_consistent and executable_closure_evidence.passed
        ),
        "verifier_consistency": (
            projection_ids_consistent and bool(verifier_id) and bool(verifier_version)
        ),
        "recursive_noninterference": noninterference,
        "state_and_lineage_closure": state_lineage,
        "destructive_mutation_rejection": (
            audit_identity_consistent and destructive_mutation_evidence.passed
        ),
    }
    blockers = tuple(sorted(name for name, passed in gates.items() if not passed))
    values: dict[str, Any] = {
        "joint_compilation_id": joint.artifact_id,
        "omega_context_id": joint.omega.context_id,
        "omega_component_manifest_id": joint.component_manifest.manifest_id,
        "state_space_compilation_id": state_space.compilation_id,
        "runtime_projections": tuple(sorted(runtime_projections, key=lambda item: item.runtime_id)),
        "verifier_id": verifier_id,
        "verifier_version": verifier_version,
        "state_mapper_version": TRAJECTORY_CANONICALIZER_VERSION,
        "materialization_contract_id": materialization_contract_id,
        "materialization_contract_version": materialization_contract_version,
        "public_sufficiency_evidence": public_sufficiency_evidence,
        "executable_closure_evidence": executable_closure_evidence,
        "destructive_mutation_evidence": destructive_mutation_evidence,
        "gates": dict(sorted(gates.items())),
        "status": "blocked" if blockers else "admitted",
        "blockers": blockers,
        "next_transition": (
            "joint_compilation_repair_only" if blockers else "agent_state_discovery"
        ),
        "schema_version": JOINT_COMPILATION_ADMISSION_VERSION,
    }
    provisional = JointCompilationAdmissionArtifact.model_construct(
        admission_id="pending", **values
    )
    return JointCompilationAdmissionArtifact(
        admission_id=joint_compilation_admission_id(provisional),
        **values,
    )


def runtime_public_projection_id(value: RuntimePublicProjection) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"projection_id"}),
        prefix="joint_runtime_public_projection:",
    )


def joint_compilation_audit_evidence_id(value: JointCompilationAuditEvidence) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"evidence_id"}),
        prefix="joint_compilation_audit_evidence:",
    )


def joint_compilation_admission_id(value: JointCompilationAdmissionArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"admission_id"}),
        prefix="joint_compilation_admission:",
    )


def _projection_leaks_oracle(
    projection: RuntimePublicProjection,
    artifacts: CompiledProofCarryingArtifacts,
) -> bool:
    serialized = json.dumps(
        projection.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    canonical_public = json.dumps(
        artifacts.public_artifact.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
    )
    task = artifacts.joint_compilation.omega.task
    secrets = (
        artifacts.joint_compilation.omega.oracle_specification.specification_id,
        artifacts.joint_compilation.omega.evidence_bundle.bundle_id,
        artifacts.joint_compilation.omega.proof_graph.graph_id,
        artifacts.joint_compilation.omega.proof_graph.graph_hash,
        task.oracle.task_program.program_id,
        task.oracle.task_program.program_hash,
        artifacts.joint_compilation.omega.quality_contract.contract_id,
        artifacts.joint_compilation.omega.quality_contract.contract_hash,
        *task.oracle.gold_evidence_ids,
    )
    return any(value and value in serialized and value not in canonical_public for value in secrets)
