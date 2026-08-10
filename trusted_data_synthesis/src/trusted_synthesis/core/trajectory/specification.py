from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.contracts.schema import QualityContract
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.schema import TaskPackage, TaskRequirement
from trusted_synthesis.core.trajectory.schema import ActionType, Trajectory
from trusted_synthesis.hashing import canonical_hash

ORACLE_EXECUTION_SPECIFICATION_VERSION = "oracle_execution_specification.v1"
VERIFICATION_CONTEXT_VERSION = "trajectory_verification_context.v1"
OMEGA_COMPONENT_MANIFEST_VERSION = "omega_component_manifest.v1"
JOINT_COMPILATION_ARTIFACT_VERSION = "joint_compilation_artifact.v1"


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


@dataclass(frozen=True)
class ReferenceExecutionIdentity:
    """Minimal immutable identity accepted in place of a full reference Trajectory."""

    trajectory_id: str
    trajectory_hash: str


class OracleExecutionSpecification(FrozenModel):
    """Hidden constraints defining valid executions, not one privileged trajectory."""

    specification_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    evidence_bundle_hash: str = Field(min_length=1)
    public_corpus_hash: str = Field(min_length=1)
    proof_graph_hash: str = Field(min_length=1)
    task_program_hash: str = Field(min_length=1)
    quality_contract_hash: str = Field(min_length=1)
    required_evidence_ids: tuple[str, ...] = Field(min_length=1)
    required_actions: tuple[ActionType, ...] = Field(min_length=1)
    allowed_tools: tuple[str, ...] = Field(min_length=1)
    answer_schema_hash: str = Field(min_length=1)
    quality_clause_ids: tuple[str, ...] = Field(min_length=1)
    reference_example_ids: tuple[str, ...] = Field(min_length=1)
    reference_example_hashes: tuple[str, ...] = Field(min_length=1)
    validity_rule: str = "candidate_workflow_and_quality_contract_all_pass"
    schema_version: str = ORACLE_EXECUTION_SPECIFICATION_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> OracleExecutionSpecification:
        if len(self.required_evidence_ids) != len(set(self.required_evidence_ids)):
            raise ValueError("Oracle execution evidence IDs must be unique")
        if len(self.required_actions) != len(set(self.required_actions)):
            raise ValueError("Oracle execution actions must be unique")
        if len(self.reference_example_ids) != len(self.reference_example_hashes):
            raise ValueError("reference example IDs and hashes must align")
        if len(self.reference_example_ids) != len(set(self.reference_example_ids)):
            raise ValueError("reference execution examples must be unique")
        if self.specification_id != oracle_execution_specification_id(self):
            raise ValueError("Oracle execution specification identity is invalid")
        return self


class TrajectoryVerificationContext(FrozenModel):
    """Omega_x = (Evidence, Program, Proof Graph, Quality Contract)."""

    context_id: str = Field(min_length=1)
    task: TaskPackage
    evidence_bundle: EvidenceBundle
    public_corpus: EvidenceCorpus
    proof_graph: ProofGraph
    quality_contract: QualityContract
    oracle_specification: OracleExecutionSpecification
    schema_version: str = VERIFICATION_CONTEXT_VERSION

    @model_validator(mode="after")
    def validate_boundary(self) -> TrajectoryVerificationContext:
        if self.quality_contract.task_id != self.task.task_id:
            raise ValueError("verification Quality Contract belongs to another task")
        if (
            self.proof_graph.graph_id != self.task.oracle.proof_graph_id
            or self.proof_graph.graph_hash != self.task.oracle.proof_graph_hash
        ):
            raise ValueError("verification Proof Graph does not match the Oracle contract")
        corpus_by_id = self.public_corpus.by_id()
        bundle_by_id = {item.evidence_id: item for item in self.evidence_bundle.evidence}
        for evidence_id in self.task.oracle.gold_evidence_ids:
            if (
                evidence_id not in bundle_by_id
                or corpus_by_id.get(evidence_id) != bundle_by_id[evidence_id]
            ):
                raise ValueError("verification Evidence boundary is incomplete or mutated")
        expected_spec = make_oracle_execution_specification(
            self.task,
            self.evidence_bundle,
            self.public_corpus,
            self.proof_graph,
            self.quality_contract,
            reference_examples=tuple(
                ReferenceExecutionIdentity(item, digest)
                for item, digest in zip(
                    self.oracle_specification.reference_example_ids,
                    self.oracle_specification.reference_example_hashes,
                    strict=True,
                )
            ),
        )
        if expected_spec != self.oracle_specification:
            raise ValueError("verification context does not reproduce its Oracle specification")
        if self.context_id != trajectory_verification_context_id(self):
            raise ValueError("trajectory verification context identity is invalid")
        return self


class OmegaComponentManifest(FrozenModel):
    """Explicit, replayable identity of Omega_x = (E_x, P_x, G_x, Q_x)."""

    manifest_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    task_hash: str = Field(min_length=1)
    evidence_bundle_id: str = Field(min_length=1)
    evidence_bundle_hash: str = Field(min_length=1)
    public_corpus_id: str = Field(min_length=1)
    public_corpus_hash: str = Field(min_length=1)
    task_program_id: str = Field(min_length=1)
    task_program_hash: str = Field(min_length=1)
    proof_graph_id: str = Field(min_length=1)
    proof_graph_hash: str = Field(min_length=1)
    quality_contract_id: str = Field(min_length=1)
    quality_contract_hash: str = Field(min_length=1)
    oracle_specification_id: str = Field(min_length=1)
    schema_version: str = OMEGA_COMPONENT_MANIFEST_VERSION

    @model_validator(mode="after")
    def validate_identity(self) -> OmegaComponentManifest:
        if self.manifest_id != omega_component_manifest_id(self):
            raise ValueError("Omega component manifest identity is invalid")
        return self


class JointCompilationArtifact(FrozenModel):
    """First-class output of joint compilation, including the complete Omega_x."""

    artifact_id: str = Field(min_length=1)
    omega: TrajectoryVerificationContext
    component_manifest: OmegaComponentManifest
    compiler_version: str = Field(min_length=1)
    schema_version: str = JOINT_COMPILATION_ARTIFACT_VERSION

    @model_validator(mode="after")
    def validate_compilation(self) -> JointCompilationArtifact:
        expected = make_omega_component_manifest(self.omega)
        if self.component_manifest != expected:
            raise ValueError("joint compilation does not reproduce its Omega component manifest")
        if self.artifact_id != joint_compilation_artifact_id(self):
            raise ValueError("joint compilation artifact identity is invalid")
        return self


def make_oracle_execution_specification(
    task: TaskPackage,
    evidence_bundle: EvidenceBundle,
    public_corpus: EvidenceCorpus,
    proof_graph: ProofGraph,
    quality_contract: QualityContract,
    *,
    reference_examples: Iterable[Trajectory | ReferenceExecutionIdentity],
) -> OracleExecutionSpecification:
    references = tuple(reference_examples)
    if not references:
        raise ValueError("an Oracle execution specification needs an auditable reference example")
    values = {
        "task_id": task.task_id,
        "evidence_bundle_hash": evidence_bundle.bundle_hash,
        "public_corpus_hash": public_corpus.corpus_hash,
        "proof_graph_hash": proof_graph.graph_hash,
        "task_program_hash": task.oracle.task_program.program_hash,
        "quality_contract_hash": quality_contract.contract_hash,
        "required_evidence_ids": tuple(sorted(task.oracle.gold_evidence_ids)),
        "required_actions": _required_actions(task),
        "allowed_tools": tuple(sorted(task.public.allowed_tools)),
        "answer_schema_hash": canonical_hash(
            task.public.answer_schema,
            prefix="oracle_answer_schema:",
        ),
        "quality_clause_ids": tuple(item.clause_id for item in quality_contract.clauses),
        "reference_example_ids": tuple(item.trajectory_id for item in references),
        "reference_example_hashes": tuple(item.trajectory_hash for item in references),
        "schema_version": ORACLE_EXECUTION_SPECIFICATION_VERSION,
    }
    provisional = OracleExecutionSpecification.model_construct(
        specification_id="pending",
        **values,
    )
    return OracleExecutionSpecification(
        specification_id=oracle_execution_specification_id(provisional),
        **values,
    )


def make_trajectory_verification_context(
    task: TaskPackage,
    evidence_bundle: EvidenceBundle,
    public_corpus: EvidenceCorpus,
    proof_graph: ProofGraph,
    quality_contract: QualityContract,
    oracle_specification: OracleExecutionSpecification,
) -> TrajectoryVerificationContext:
    values = {
        "task": task,
        "evidence_bundle": evidence_bundle,
        "public_corpus": public_corpus,
        "proof_graph": proof_graph,
        "quality_contract": quality_contract,
        "oracle_specification": oracle_specification,
        "schema_version": VERIFICATION_CONTEXT_VERSION,
    }
    provisional = TrajectoryVerificationContext.model_construct(
        context_id="pending",
        **values,
    )
    return TrajectoryVerificationContext(
        context_id=trajectory_verification_context_id(provisional),
        **values,
    )


def make_omega_component_manifest(
    context: TrajectoryVerificationContext,
) -> OmegaComponentManifest:
    values = {
        "task_id": context.task.task_id,
        "task_hash": context.task.task_hash,
        "evidence_bundle_id": context.evidence_bundle.bundle_id,
        "evidence_bundle_hash": context.evidence_bundle.bundle_hash,
        "public_corpus_id": context.public_corpus.corpus_id,
        "public_corpus_hash": context.public_corpus.corpus_hash,
        "task_program_id": context.task.oracle.task_program.program_id,
        "task_program_hash": context.task.oracle.task_program.program_hash,
        "proof_graph_id": context.proof_graph.graph_id,
        "proof_graph_hash": context.proof_graph.graph_hash,
        "quality_contract_id": context.quality_contract.contract_id,
        "quality_contract_hash": context.quality_contract.contract_hash,
        "oracle_specification_id": context.oracle_specification.specification_id,
        "schema_version": OMEGA_COMPONENT_MANIFEST_VERSION,
    }
    provisional = OmegaComponentManifest.model_construct(manifest_id="pending", **values)
    return OmegaComponentManifest(
        manifest_id=omega_component_manifest_id(provisional),
        **values,
    )


def make_joint_compilation_artifact(
    context: TrajectoryVerificationContext,
    *,
    compiler_version: str,
) -> JointCompilationArtifact:
    values = {
        "omega": context,
        "component_manifest": make_omega_component_manifest(context),
        "compiler_version": compiler_version,
        "schema_version": JOINT_COMPILATION_ARTIFACT_VERSION,
    }
    provisional = JointCompilationArtifact.model_construct(artifact_id="pending", **values)
    return JointCompilationArtifact(
        artifact_id=joint_compilation_artifact_id(provisional),
        **values,
    )


def oracle_execution_specification_id(value: OracleExecutionSpecification) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"specification_id"}),
        prefix="oracle_execution_specification:",
    )


def trajectory_verification_context_id(value: TrajectoryVerificationContext) -> str:
    identity = {
        "task_hash": value.task.task_hash,
        "evidence_bundle_hash": value.evidence_bundle.bundle_hash,
        "public_corpus_hash": value.public_corpus.corpus_hash,
        "proof_graph_hash": value.proof_graph.graph_hash,
        "quality_contract_hash": value.quality_contract.contract_hash,
        "oracle_specification_id": value.oracle_specification.specification_id,
        "schema_version": value.schema_version,
    }
    return canonical_hash(identity, prefix="trajectory_verification_context:")


def omega_component_manifest_id(value: OmegaComponentManifest) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"manifest_id"}),
        prefix="omega_component_manifest:",
    )


def joint_compilation_artifact_id(value: JointCompilationArtifact) -> str:
    return canonical_hash(
        value.model_dump(mode="json", exclude={"artifact_id"}),
        prefix="joint_compilation_artifact:",
    )


def _required_actions(task: TaskPackage) -> tuple[ActionType, ...]:
    mapping = {
        TaskRequirement.RETRIEVE_EVIDENCE: ActionType.SEARCH,
        TaskRequirement.SELECT_EVIDENCE: ActionType.SELECT_EVIDENCE,
        TaskRequirement.CALCULATE: ActionType.CALCULATE,
        TaskRequirement.VERIFY_RESULT: ActionType.VERIFY,
    }
    actions = {ActionType.PLAN, ActionType.ANSWER}
    actions.update(
        mapping[requirement] for requirement in task.public.requirements if requirement in mapping
    )
    return tuple(sorted(actions, key=lambda item: item.value))
