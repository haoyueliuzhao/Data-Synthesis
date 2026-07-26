from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trusted_synthesis.core.evaluation.contracts.schema import QualityContract
from trusted_synthesis.core.evaluation.schema import QualityAssessment
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.task.schema import TaskPackage, TaskPublicSpec
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


class ProofCertificate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    certificate_id: str
    certificate_hash: str
    task_id: str
    task_package_hash: str
    evidence_bundle_hash: str
    proof_graph_hash: str
    task_program_hash: str
    quality_contract_hash: str
    expected_output_hash: str
    reference_execution_hash: str
    operation_manifest_hash: str
    domain_plugin_manifest_hash: str
    source_grounding_manifest_hash: str | None = None
    compiler_version: str
    schema_version: str = "proof_certificate.v1"

    @model_validator(mode="after")
    def validate_certificate(self) -> ProofCertificate:
        certificate_id, certificate_hash = proof_certificate_hashes(
            task_id=self.task_id,
            task_package_hash=self.task_package_hash,
            evidence_bundle_hash=self.evidence_bundle_hash,
            proof_graph_hash=self.proof_graph_hash,
            task_program_hash=self.task_program_hash,
            quality_contract_hash=self.quality_contract_hash,
            expected_output_hash=self.expected_output_hash,
            reference_execution_hash=self.reference_execution_hash,
            operation_manifest_hash=self.operation_manifest_hash,
            domain_plugin_manifest_hash=self.domain_plugin_manifest_hash,
            source_grounding_manifest_hash=self.source_grounding_manifest_hash,
            compiler_version=self.compiler_version,
            schema_version=self.schema_version,
        )
        if self.certificate_id != certificate_id or self.certificate_hash != certificate_hash:
            raise ValueError("proof certificate identity or hash is invalid")
        return self


class ProofCarryingSample(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    task_id: str
    task_package_hash: str
    evidence_bundle_id: str
    evidence_bundle_hash: str
    proof_graph_id: str
    proof_graph_hash: str
    task_program_id: str
    task_program_hash: str
    reference_trajectory_id: str
    reference_trajectory_hash: str
    quality_contract_id: str
    quality_contract_hash: str
    certificate: ProofCertificate
    pattern_id: str
    binding_id: str
    difficulty_profile: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "proof_carrying_sample.v1"

    @model_validator(mode="after")
    def validate_sample(self) -> ProofCarryingSample:
        if self.certificate.task_id != self.task_id:
            raise ValueError("proof certificate task does not match sample")
        expected = {
            "task_package_hash": self.task_package_hash,
            "evidence_bundle_hash": self.evidence_bundle_hash,
            "proof_graph_hash": self.proof_graph_hash,
            "task_program_hash": self.task_program_hash,
            "quality_contract_hash": self.quality_contract_hash,
            "reference_execution_hash": self.reference_trajectory_hash,
        }
        observed = {
            key: getattr(self.certificate, key) for key in expected
        }
        if observed != expected:
            raise ValueError("proof certificate does not bind the sample artifacts")
        identity = proof_carrying_sample_identity(
            task_id=self.task_id,
            task_package_hash=self.task_package_hash,
            evidence_bundle_id=self.evidence_bundle_id,
            evidence_bundle_hash=self.evidence_bundle_hash,
            proof_graph_id=self.proof_graph_id,
            proof_graph_hash=self.proof_graph_hash,
            task_program_id=self.task_program_id,
            task_program_hash=self.task_program_hash,
            reference_trajectory_id=self.reference_trajectory_id,
            reference_trajectory_hash=self.reference_trajectory_hash,
            quality_contract_id=self.quality_contract_id,
            quality_contract_hash=self.quality_contract_hash,
            certificate_hash=self.certificate.certificate_hash,
            pattern_id=self.pattern_id,
            binding_id=self.binding_id,
            difficulty_profile=self.difficulty_profile,
            metadata=self.metadata,
            schema_version=self.schema_version,
        )
        if self.sample_id != canonical_hash(identity, prefix="proof_carrying_sample:"):
            raise ValueError("proof-carrying sample identity is invalid")
        return self


class ProofCarryingPublicArtifact(BaseModel):
    """Serializable model-facing view; no Oracle, evidence IDs, or reference answer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    sample_id: str
    task_public: TaskPublicSpec
    certificate_id: str
    certificate_hash: str
    pattern_id: str
    difficulty_profile: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompiledProofCarryingArtifacts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sample: ProofCarryingSample
    public_artifact: ProofCarryingPublicArtifact
    task: TaskPackage
    evidence_bundle: EvidenceBundle
    proof_graph: ProofGraph
    reference_trajectory: Trajectory
    reference_assessment: QualityAssessment
    quality_contract: QualityContract


def make_proof_certificate(
    *,
    task_id: str,
    task_package_hash: str,
    evidence_bundle_hash: str,
    proof_graph_hash: str,
    task_program_hash: str,
    quality_contract_hash: str,
    expected_output_hash: str,
    reference_execution_hash: str,
    operation_manifest_hash: str,
    domain_plugin_manifest_hash: str,
    source_grounding_manifest_hash: str | None,
    compiler_version: str,
) -> ProofCertificate:
    certificate_id, certificate_hash = proof_certificate_hashes(
        task_id=task_id,
        task_package_hash=task_package_hash,
        evidence_bundle_hash=evidence_bundle_hash,
        proof_graph_hash=proof_graph_hash,
        task_program_hash=task_program_hash,
        quality_contract_hash=quality_contract_hash,
        expected_output_hash=expected_output_hash,
        reference_execution_hash=reference_execution_hash,
        operation_manifest_hash=operation_manifest_hash,
        domain_plugin_manifest_hash=domain_plugin_manifest_hash,
        source_grounding_manifest_hash=source_grounding_manifest_hash,
        compiler_version=compiler_version,
        schema_version="proof_certificate.v1",
    )
    return ProofCertificate(
        certificate_id=certificate_id,
        certificate_hash=certificate_hash,
        task_id=task_id,
        task_package_hash=task_package_hash,
        evidence_bundle_hash=evidence_bundle_hash,
        proof_graph_hash=proof_graph_hash,
        task_program_hash=task_program_hash,
        quality_contract_hash=quality_contract_hash,
        expected_output_hash=expected_output_hash,
        reference_execution_hash=reference_execution_hash,
        operation_manifest_hash=operation_manifest_hash,
        domain_plugin_manifest_hash=domain_plugin_manifest_hash,
        source_grounding_manifest_hash=source_grounding_manifest_hash,
        compiler_version=compiler_version,
    )


def proof_certificate_hashes(**identity: Any) -> tuple[str, str]:
    return (
        canonical_hash(identity, prefix="proof_certificate:"),
        canonical_hash(identity, prefix="proof_certificate_hash:"),
    )


def proof_carrying_sample_identity(**identity: Any) -> dict[str, Any]:
    return identity
