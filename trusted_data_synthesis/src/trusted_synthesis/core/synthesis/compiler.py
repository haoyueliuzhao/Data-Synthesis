from __future__ import annotations

from typing import Any

from trusted_synthesis.core.evaluation.contracts.compiler import QualityContractCompiler
from trusted_synthesis.core.evaluation.evaluator import ReferenceQualityEvaluator
from trusted_synthesis.core.evaluation.schema import QualityAssessment, ReleaseDecision
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.plugins import (
    DomainPluginSet,
    SemanticPolicyProtocol,
    SourceGroundingVerifierProtocol,
)
from trusted_synthesis.core.synthesis.certificate import build_proof_certificate
from trusted_synthesis.core.synthesis.schema import (
    CompiledProofCarryingArtifacts,
    ProofCarryingPublicArtifact,
    ProofCarryingSample,
    proof_carrying_sample_identity,
)
from trusted_synthesis.core.synthesis.validation import validate_compiled_artifacts
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.generator import ReferenceWorkflowCompiler
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.core.trajectory.verifier import ReferenceWorkflowVerifier
from trusted_synthesis.hashing import canonical_hash

PROOF_CARRYING_COMPILER_VERSION = "proof_carrying_compiler.v3"


class ProofCarryingSampleCompiler:
    """Jointly bind an existing task package to proof, reference, and quality artifacts."""

    def __init__(
        self,
        operation_registry: OperationRegistry,
        quality_contract_compiler: QualityContractCompiler,
        domain_plugin_set: DomainPluginSet,
        *,
        semantic_policy: SemanticPolicyProtocol | None = None,
        source_grounding_verifier: SourceGroundingVerifierProtocol | None = None,
    ) -> None:
        self._operation_registry = operation_registry
        self._quality_contract_compiler = quality_contract_compiler
        self._domain_plugin_set = domain_plugin_set
        self._source_grounding_verifier = source_grounding_verifier
        self._reference_compiler = ReferenceWorkflowCompiler(operation_registry)
        self._reference_evaluator = ReferenceQualityEvaluator(
            semantic_policy=semantic_policy,
            source_grounding_verifier=source_grounding_verifier,
            workflow_verifier=ReferenceWorkflowVerifier(operation_registry),
        )

    def compile(
        self,
        task: TaskPackage,
        evidence_bundle: EvidenceBundle,
        proof_graph: ProofGraph,
        *,
        pattern_id: str | None = None,
        binding_id: str | None = None,
        difficulty_profile: dict[str, float] | None = None,
        metadata: dict[str, Any] | None = None,
        reference_trajectory: Trajectory | None = None,
        reference_assessment: QualityAssessment | None = None,
    ) -> CompiledProofCarryingArtifacts:
        if self._domain_plugin_set.domain != task.public.domain:
            raise ValueError("domain plugin set does not match the task")
        quality_contract = self._quality_contract_compiler.compile(
            task, evidence_bundle, proof_graph
        )
        provider_identity = self._domain_plugin_set.quality_provider_identity
        contract_provider = quality_contract.domain_provider_identity
        if provider_identity != contract_provider:
            raise ValueError("quality contract provider is not frozen by the domain plugin set")
        reference = reference_trajectory or self._reference_compiler.compile(task, evidence_bundle)
        assessment = reference_assessment or self._reference_evaluator.evaluate(
            task, evidence_bundle, proof_graph, reference
        )
        if assessment.decision != ReleaseDecision.ACCEPTED:
            raise ValueError("reference workflow did not satisfy deterministic quality gates")
        if (
            assessment.task_id != task.task_id
            or assessment.trajectory_id != reference.trajectory_id
        ):
            raise ValueError("reference assessment identity does not match compiled artifacts")
        certificate = build_proof_certificate(
            task=task,
            evidence_bundle=evidence_bundle,
            proof_graph=proof_graph,
            reference_trajectory=reference,
            quality_contract=quality_contract,
            operation_registry=self._operation_registry,
            domain_plugin_set=self._domain_plugin_set,
            source_grounding_verifier=self._source_grounding_verifier,
            compiler_version=PROOF_CARRYING_COMPILER_VERSION,
        )
        pattern_identity = task.public.metadata.get("task_pattern")
        binding_identity = task.oracle.selection_contract.get("pattern_binding")
        declared_pattern_id = (
            str(pattern_identity.get("pattern_id")) if isinstance(pattern_identity, dict) else None
        )
        declared_binding_id = (
            str(binding_identity.get("binding_id")) if isinstance(binding_identity, dict) else None
        )
        if pattern_id is not None and declared_pattern_id not in (None, pattern_id):
            raise ValueError("sample pattern ID disagrees with the compiled task pattern")
        if binding_id is not None and declared_binding_id not in (None, binding_id):
            raise ValueError("sample binding ID disagrees with the compiled evidence binding")
        pattern = pattern_id or declared_pattern_id or task.public.task_type
        binding = (
            binding_id
            or declared_binding_id
            or canonical_hash(
                {
                    "task_id": task.task_id,
                    "evidence_semantic_keys": sorted(
                        item.semantic_key
                        for item in evidence_bundle.evidence
                        if item.evidence_id in set(task.oracle.gold_evidence_ids)
                    ),
                },
                prefix="evidence_binding:",
            )
        )
        declared_difficulty = task.public.metadata.get("difficulty_profile")
        difficulty = difficulty_profile or (
            {
                key: float(value)
                for key, value in declared_difficulty.items()
                if isinstance(value, (int, float))
            }
            if isinstance(declared_difficulty, dict)
            else {
                "evidence_count": float(len(task.oracle.gold_evidence_ids)),
                "program_node_count": float(len(task.oracle.task_program.nodes)),
                "program_depth": float(_program_depth(task)),
            }
        )
        pattern_hash = (
            str(pattern_identity.get("pattern_hash"))
            if isinstance(pattern_identity, dict)
            else None
        )
        binding_hash = (
            str(binding_identity.get("binding_hash"))
            if isinstance(binding_identity, dict)
            else None
        )
        task_pattern_compiler_version = (
            str(pattern_identity.get("compiler_version"))
            if isinstance(pattern_identity, dict)
            else None
        )
        sample_metadata = metadata or {}
        identity = proof_carrying_sample_identity(
            task_id=task.task_id,
            task_package_hash=task.task_hash,
            evidence_bundle_id=evidence_bundle.bundle_id,
            evidence_bundle_hash=evidence_bundle.bundle_hash,
            proof_graph_id=proof_graph.graph_id,
            proof_graph_hash=proof_graph.graph_hash,
            task_program_id=task.oracle.task_program.program_id,
            task_program_hash=task.oracle.task_program.program_hash,
            reference_trajectory_id=reference.trajectory_id,
            reference_trajectory_hash=reference.trajectory_hash,
            quality_contract_id=quality_contract.contract_id,
            quality_contract_hash=quality_contract.contract_hash,
            certificate_hash=certificate.certificate_hash,
            pattern_id=pattern,
            binding_id=binding,
            pattern_hash=pattern_hash,
            binding_hash=binding_hash,
            task_pattern_compiler_version=task_pattern_compiler_version,
            difficulty_profile=difficulty,
            metadata=sample_metadata,
            schema_version="proof_carrying_sample.v3",
        )
        sample = ProofCarryingSample(
            sample_id=canonical_hash(identity, prefix="proof_carrying_sample:"),
            task_id=task.task_id,
            task_package_hash=task.task_hash,
            evidence_bundle_id=evidence_bundle.bundle_id,
            evidence_bundle_hash=evidence_bundle.bundle_hash,
            proof_graph_id=proof_graph.graph_id,
            proof_graph_hash=proof_graph.graph_hash,
            task_program_id=task.oracle.task_program.program_id,
            task_program_hash=task.oracle.task_program.program_hash,
            reference_trajectory_id=reference.trajectory_id,
            reference_trajectory_hash=reference.trajectory_hash,
            quality_contract_id=quality_contract.contract_id,
            quality_contract_hash=quality_contract.contract_hash,
            certificate=certificate,
            pattern_id=pattern,
            binding_id=binding,
            pattern_hash=pattern_hash,
            binding_hash=binding_hash,
            task_pattern_compiler_version=task_pattern_compiler_version,
            difficulty_profile=difficulty,
            metadata=sample_metadata,
        )
        public_artifact = ProofCarryingPublicArtifact(
            sample_id=sample.sample_id,
            task_public=task.public,
            certificate_id=certificate.certificate_id,
            certificate_hash=certificate.certificate_hash,
            pattern_id=pattern,
            pattern_hash=pattern_hash,
            task_pattern_compiler_version=task_pattern_compiler_version,
            difficulty_profile=difficulty,
            metadata={"schema_version": sample.schema_version},
        )
        artifacts = CompiledProofCarryingArtifacts(
            sample=sample,
            public_artifact=public_artifact,
            task=task,
            evidence_bundle=evidence_bundle,
            proof_graph=proof_graph,
            reference_trajectory=reference,
            reference_assessment=assessment,
            quality_contract=quality_contract,
        )
        validate_compiled_artifacts(artifacts)
        return artifacts


def _program_depth(task: TaskPackage) -> int:
    depths: dict[str, int] = {}
    for node in task.oracle.task_program.nodes:
        depths[node.node_id] = 1 + max((depths[item] for item in node.dependencies), default=0)
    return max(depths.values())
