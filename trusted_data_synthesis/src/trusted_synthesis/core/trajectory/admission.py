from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.audit_artifacts import AtomicAuditCaseResult
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

JOINT_COMPILATION_ADMISSION_VERSION = "joint_compilation_admission.v2"
RUNTIME_PUBLIC_PROJECTION_VERSION = "joint_runtime_public_projection.v2"
RUNTIME_AUTHORITY_POLICY_VERSION = "runtime_authority_policy.v1"
EXECUTABLE_COMPONENT_MANIFEST_VERSION = "executable_component_manifest.v1"
JOINT_COMPILATION_AUDIT_EVIDENCE_VERSION = "joint_compilation_audit_evidence.v2"

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


class RuntimeAuthorityPolicy(FrozenModel):
    policy_id: str = Field(min_length=1)
    runtime_id: str = Field(min_length=1)
    action_scheduler: Literal["host_registered_sequence", "model"]
    tool_selection_authority: Literal["host_registered_tool", "model"]
    argument_authority: Literal["model"] = "model"
    repair_authority: Literal["host_abort", "model"]
    stopping_authority: Literal["host_budget", "model"]
    public_observation_delivery: Literal["stepwise"] = "stepwise"
    hidden_oracle_access: Literal[False] = False
    schema_version: str = RUNTIME_AUTHORITY_POLICY_VERSION

    @model_validator(mode="after")
    def validate_policy(self) -> RuntimeAuthorityPolicy:
        if self.policy_id != runtime_authority_policy_id(self):
            raise ValueError("runtime authority policy identity is invalid")
        return self


class ExecutableComponentManifest(FrozenModel):
    manifest_id: str = Field(min_length=1)
    component_kind: Literal["independent_verifier", "trajectory_materializer"]
    component_id: str = Field(min_length=1)
    component_version: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    implementation_manifest_hash: str = Field(min_length=1)
    input_schema_hash: str = Field(min_length=1)
    output_schema_hash: str = Field(min_length=1)
    replay_case: AtomicAuditCaseResult
    schema_version: str = EXECUTABLE_COMPONENT_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_manifest(self) -> ExecutableComponentManifest:
        expected_check = f"{self.component_kind}_contract_replay"
        expected_primary_manifest = {
            "component_id": self.component_id,
            "component_version": self.component_version,
            "check_id": expected_check,
        }
        expected_replay_manifest = {
            "component_id": f"{self.component_id}.independent",
            "component_version": self.component_version,
            "check_id": expected_check,
        }
        if (
            self.replay_case.check_id != expected_check
            or self.replay_case.subject_id != self.component_id
            or self.joint_compilation_id not in self.replay_case.input_artifact_ids
            or self.component_id not in self.replay_case.output_artifact_ids
            or self.implementation_manifest_hash
            != self.replay_case.implementation_manifest_hash
            or self.replay_case.implementation_manifest != expected_primary_manifest
            or self.replay_case.replay_implementation_manifest != expected_replay_manifest
            or not self.replay_case.check_passed
        ):
            raise ValueError("executable component lacks a passing bound replay")
        if self.manifest_id != executable_component_manifest_id(self):
            raise ValueError("executable component manifest identity is invalid")
        return self


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
    authority_policy: RuntimeAuthorityPolicy
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
        if self.authority_policy.runtime_id != self.runtime_id:
            raise ValueError("runtime projection uses another runtime authority policy")
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
    case_results: tuple[AtomicAuditCaseResult, ...] = Field(min_length=1)
    auditor_id: str = Field(min_length=1)
    auditor_version: str = Field(min_length=1)
    auditor_manifest_hash: str = Field(min_length=1)
    schema_version: str = JOINT_COMPILATION_AUDIT_EVIDENCE_VERSION

    @model_validator(mode="after")
    def validate_evidence(self) -> JointCompilationAuditEvidence:
        expected = {
            "public_sufficiency": PUBLIC_SUFFICIENCY_CHECKS,
            "executable_closure": EXECUTABLE_CLOSURE_CHECKS,
            "destructive_mutation": DESTRUCTIVE_MUTATION_CHECKS,
        }[self.audit_kind]
        observed = tuple(sorted(item.check_id for item in self.case_results))
        if observed != tuple(sorted(expected)) or len(observed) != len(set(observed)):
            raise ValueError("Joint Compilation audit checks are incomplete")
        if any(
            item.subject_id != self.joint_compilation_id
            or self.joint_compilation_id not in item.input_artifact_ids
            for item in self.case_results
        ):
            raise ValueError("Joint Compilation audit case crosses compilation identities")
        if any(
            item.implementation_manifest
            != {
                "auditor_id": self.auditor_id,
                "auditor_version": self.auditor_version,
                "check_id": item.check_id,
            }
            or item.replay_implementation_manifest
            != {
                "auditor_id": f"{self.auditor_id}.independent",
                "auditor_version": self.auditor_version,
                "check_id": item.check_id,
            }
            for item in self.case_results
        ):
            raise ValueError("Joint Compilation audit case uses an unknown implementation")
        expected_manifest = canonical_hash(
            {"auditor_id": self.auditor_id, "auditor_version": self.auditor_version},
            prefix="joint_compilation_auditor_manifest:",
        )
        if self.auditor_manifest_hash != expected_manifest:
            raise ValueError("Joint Compilation auditor manifest identity is invalid")
        if self.evidence_id != joint_compilation_audit_evidence_id(self):
            raise ValueError("Joint Compilation audit Evidence identity is invalid")
        return self

    @property
    def checks(self) -> dict[str, bool]:
        return {item.check_id: item.check_passed for item in self.case_results}

    @property
    def passed(self) -> bool:
        return all(item.check_passed for item in self.case_results)


class JointCompilationAdmissionArtifact(FrozenModel):
    admission_id: str = Field(min_length=1)
    joint_compilation_id: str = Field(min_length=1)
    omega_context_id: str = Field(min_length=1)
    omega_component_manifest_id: str = Field(min_length=1)
    state_space_compilation_id: str = Field(min_length=1)
    compiled_artifacts: CompiledProofCarryingArtifacts
    state_space: TrajectoryStateSpaceCompilation
    runtime_projections: tuple[RuntimePublicProjection, ...] = Field(min_length=1)
    verifier_manifest: ExecutableComponentManifest
    state_mapper_version: str = Field(min_length=1)
    materialization_manifest: ExecutableComponentManifest
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
        validate_compiled_artifacts(self.compiled_artifacts)
        joint = self.compiled_artifacts.joint_compilation
        if (
            joint.artifact_id != self.joint_compilation_id
            or joint.omega.context_id != self.omega_context_id
            or joint.component_manifest.manifest_id != self.omega_component_manifest_id
            or self.state_space.compilation_id != self.state_space_compilation_id
        ):
            raise ValueError("Joint Compilation admission root identities are inconsistent")
        if self.state_space.joint_compilation != joint:
            raise ValueError("Joint Compilation admission embeds a detached state space")
        if self.public_sufficiency_evidence.audit_kind != "public_sufficiency":
            raise ValueError("Joint Compilation public-sufficiency Evidence kind is invalid")
        if self.executable_closure_evidence.audit_kind != "executable_closure":
            raise ValueError("Joint Compilation executable-closure Evidence kind is invalid")
        if self.destructive_mutation_evidence.audit_kind != "destructive_mutation":
            raise ValueError("Joint Compilation mutation Evidence kind is invalid")
        expected_gates = _derive_joint_admission_gates(self)
        if self.gates != expected_gates:
            raise ValueError("Joint Compilation admission gates were not derived from Evidence")
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
        if (
            self.verifier_manifest.component_kind != "independent_verifier"
            or self.materialization_manifest.component_kind != "trajectory_materializer"
            or self.verifier_manifest.joint_compilation_id != self.joint_compilation_id
            or self.materialization_manifest.joint_compilation_id != self.joint_compilation_id
        ):
            raise ValueError("Joint Compilation executable components cross identities")
        if self.admission_id != joint_compilation_admission_id(self):
            raise ValueError("Joint Compilation admission identity is invalid")
        return self


def make_runtime_public_projection(
    artifacts: CompiledProofCarryingArtifacts,
    state_space: TrajectoryStateSpaceCompilation,
    *,
    runtime_id: str,
    authority_policy: RuntimeAuthorityPolicy | None = None,
) -> RuntimePublicProjection:
    joint = artifacts.joint_compilation
    if state_space.joint_compilation_artifact_id != joint.artifact_id:
        raise ValueError("runtime projection state space is detached from Joint Compilation")
    conditions = tuple(
        state_space.public_conditions_by_variation_id[key]
        for key in sorted(state_space.public_conditions_by_variation_id)
    )
    policy = authority_policy or make_runtime_authority_policy(runtime_id)
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
        "authority_policy": policy,
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
    case_results: Sequence[AtomicAuditCaseResult],
    auditor_id: str,
    auditor_version: str,
) -> JointCompilationAuditEvidence:
    manifest_hash = canonical_hash(
        {"auditor_id": auditor_id, "auditor_version": auditor_version},
        prefix="joint_compilation_auditor_manifest:",
    )
    values = {
        "audit_kind": audit_kind,
        "joint_compilation_id": joint_compilation_id,
        "case_results": tuple(sorted(case_results, key=lambda item: item.check_id)),
        "auditor_id": auditor_id,
        "auditor_version": auditor_version,
        "auditor_manifest_hash": manifest_hash,
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
    verifier_manifest: ExecutableComponentManifest,
    materialization_manifest: ExecutableComponentManifest,
) -> JointCompilationAdmissionArtifact:
    validate_compiled_artifacts(artifacts)
    joint = artifacts.joint_compilation
    sorted_projections = tuple(sorted(runtime_projections, key=lambda item: item.runtime_id))
    values: dict[str, Any] = {
        "joint_compilation_id": joint.artifact_id,
        "omega_context_id": joint.omega.context_id,
        "omega_component_manifest_id": joint.component_manifest.manifest_id,
        "state_space_compilation_id": state_space.compilation_id,
        "compiled_artifacts": artifacts,
        "state_space": state_space,
        "runtime_projections": sorted_projections,
        "verifier_manifest": verifier_manifest,
        "state_mapper_version": TRAJECTORY_CANONICALIZER_VERSION,
        "materialization_manifest": materialization_manifest,
        "public_sufficiency_evidence": public_sufficiency_evidence,
        "executable_closure_evidence": executable_closure_evidence,
        "destructive_mutation_evidence": destructive_mutation_evidence,
        "gates": {},
        "status": "blocked",
        "blockers": (),
        "next_transition": "joint_compilation_repair_only",
        "schema_version": JOINT_COMPILATION_ADMISSION_VERSION,
    }
    gate_source = JointCompilationAdmissionArtifact.model_construct(
        admission_id="pending",
        **values,
    )
    gates = _derive_joint_admission_gates(gate_source)
    blockers = tuple(sorted(name for name, passed in gates.items() if not passed))
    values.update(
        {
            "gates": dict(sorted(gates.items())),
            "status": "blocked" if blockers else "admitted",
            "blockers": blockers,
            "next_transition": (
                "joint_compilation_repair_only" if blockers else "agent_state_discovery"
            ),
        }
    )
    provisional = JointCompilationAdmissionArtifact.model_construct(
        admission_id="pending",
        **values,
    )
    return JointCompilationAdmissionArtifact(
        admission_id=joint_compilation_admission_id(provisional),
        **values,
    )


def make_runtime_authority_policy(runtime_id: str) -> RuntimeAuthorityPolicy:
    if runtime_id == "scripted":
        authority = {
            "action_scheduler": "host_registered_sequence",
            "tool_selection_authority": "host_registered_tool",
            "repair_authority": "host_abort",
            "stopping_authority": "host_budget",
        }
    elif runtime_id == "autonomous":
        authority = {
            "action_scheduler": "model",
            "tool_selection_authority": "model",
            "repair_authority": "model",
            "stopping_authority": "model",
        }
    else:
        raise ValueError("runtime authority policy must be explicitly registered")
    values = {
        "runtime_id": runtime_id,
        **authority,
        "schema_version": RUNTIME_AUTHORITY_POLICY_VERSION,
    }
    provisional = RuntimeAuthorityPolicy.model_construct(policy_id="pending", **values)
    return RuntimeAuthorityPolicy(policy_id=runtime_authority_policy_id(provisional), **values)


def make_executable_component_manifest(
    *,
    component_kind: Literal["independent_verifier", "trajectory_materializer"],
    component_id: str,
    component_version: str,
    joint_compilation_id: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    replay_case: AtomicAuditCaseResult,
) -> ExecutableComponentManifest:
    values = {
        "component_kind": component_kind,
        "component_id": component_id,
        "component_version": component_version,
        "joint_compilation_id": joint_compilation_id,
        "implementation_manifest_hash": replay_case.implementation_manifest_hash,
        "input_schema_hash": canonical_hash(
            input_schema,
            prefix="executable_component_input_schema:",
        ),
        "output_schema_hash": canonical_hash(
            output_schema,
            prefix="executable_component_output_schema:",
        ),
        "replay_case": replay_case,
        "schema_version": EXECUTABLE_COMPONENT_MANIFEST_VERSION,
    }
    provisional = ExecutableComponentManifest.model_construct(manifest_id="pending", **values)
    return ExecutableComponentManifest(
        manifest_id=executable_component_manifest_id(provisional),
        **values,
    )


def runtime_public_projection_id(value: RuntimePublicProjection) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"projection_id"}),
        prefix="joint_runtime_public_projection:",
    )


def runtime_authority_policy_id(value: RuntimeAuthorityPolicy) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"policy_id"}),
        prefix="runtime_authority_policy:",
    )


def executable_component_manifest_id(value: ExecutableComponentManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="executable_component_manifest:",
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


def _derive_joint_admission_gates(
    admission: JointCompilationAdmissionArtifact,
) -> dict[str, bool]:
    artifacts = admission.compiled_artifacts
    joint = artifacts.joint_compilation
    state_space = admission.state_space
    semantic_closure = (
        artifacts.reference_assessment.decision == ReleaseDecision.ACCEPTED
        and not artifacts.reference_assessment.fatal_failures
        and not artifacts.reference_assessment.failed_check_ids
    )
    projection_ids_consistent = bool(admission.runtime_projections) and all(
        item.joint_compilation_id == joint.artifact_id
        and item.omega_context_id == joint.omega.context_id
        and item.task_id == joint.omega.task.task_id
        and item.state_space_compilation_id == state_space.compilation_id
        and item.public_corpus_id == joint.omega.public_corpus.corpus_id
        and item.public_corpus_hash == joint.omega.public_corpus.corpus_hash
        for item in admission.runtime_projections
    )
    evidence = (
        admission.public_sufficiency_evidence,
        admission.executable_closure_evidence,
        admission.destructive_mutation_evidence,
    )
    expected_kinds = (
        "public_sufficiency",
        "executable_closure",
        "destructive_mutation",
    )
    audit_identity_consistent = (
        tuple(item.audit_kind for item in evidence) == expected_kinds
        and all(item.joint_compilation_id == joint.artifact_id for item in evidence)
    )
    state_lineage = (
        state_space.joint_compilation_artifact_id == joint.artifact_id
        and state_space.omega_context_id == joint.omega.context_id
        and state_space.omega_component_manifest == joint.component_manifest
        and admission.materialization_manifest.component_kind == "trajectory_materializer"
        and admission.materialization_manifest.joint_compilation_id == joint.artifact_id
        and admission.materialization_manifest.replay_case.check_passed
    )
    verifier_consistency = (
        projection_ids_consistent
        and admission.verifier_manifest.component_kind == "independent_verifier"
        and admission.verifier_manifest.joint_compilation_id == joint.artifact_id
        and admission.verifier_manifest.replay_case.check_passed
    )
    noninterference = projection_ids_consistent and all(
        not _projection_leaks_oracle(item, artifacts) for item in admission.runtime_projections
    )
    return dict(
        sorted(
            {
                "semantic_closure": semantic_closure,
                "public_sufficiency": (
                    audit_identity_consistent
                    and admission.public_sufficiency_evidence.passed
                ),
                "executable_closure": (
                    semantic_closure
                    and audit_identity_consistent
                    and admission.executable_closure_evidence.passed
                    and admission.materialization_manifest.replay_case.check_passed
                ),
                "verifier_consistency": verifier_consistency,
                "recursive_noninterference": noninterference,
                "state_and_lineage_closure": state_lineage,
                "destructive_mutation_rejection": (
                    audit_identity_consistent
                    and admission.destructive_mutation_evidence.passed
                ),
            }.items()
        )
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
