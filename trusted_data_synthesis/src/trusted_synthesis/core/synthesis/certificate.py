from __future__ import annotations

from trusted_synthesis.core.evaluation.contracts.schema import QualityContract
from trusted_synthesis.core.evidence.schema import EvidenceBundle
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.operations.registry import OperationRegistry
from trusted_synthesis.core.plugins import (
    DomainPluginSet,
    SourceGroundingVerifierProtocol,
)
from trusted_synthesis.core.synthesis.schema import ProofCertificate, make_proof_certificate
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.schema import Trajectory
from trusted_synthesis.hashing import canonical_hash


def build_proof_certificate(
    *,
    task: TaskPackage,
    evidence_bundle: EvidenceBundle,
    proof_graph: ProofGraph,
    reference_trajectory: Trajectory,
    quality_contract: QualityContract,
    operation_registry: OperationRegistry,
    domain_plugin_set: DomainPluginSet,
    source_grounding_verifier: SourceGroundingVerifierProtocol | None,
    compiler_version: str,
) -> ProofCertificate:
    grounding_hash = None
    if source_grounding_verifier is not None:
        grounding_hash = canonical_hash(
            {
                "verifier_id": source_grounding_verifier.verifier_id,
                "verifier_version": source_grounding_verifier.verifier_version,
            },
            prefix="source_grounding_manifest:",
        )
    pattern_identity = task.public.metadata.get("task_pattern")
    binding_identity = task.oracle.selection_contract.get("pattern_binding")
    task_pattern_hash = None
    evidence_binding_hash = None
    task_pattern_compiler_version = None
    if isinstance(pattern_identity, dict) and isinstance(binding_identity, dict):
        task_pattern_hash = str(pattern_identity.get("pattern_hash") or "") or None
        evidence_binding_hash = str(binding_identity.get("binding_hash") or "") or None
        task_pattern_compiler_version = (
            str(pattern_identity.get("compiler_version") or "") or None
        )
    return make_proof_certificate(
        task_id=task.task_id,
        task_package_hash=task.task_hash,
        evidence_bundle_hash=evidence_bundle.bundle_hash,
        proof_graph_hash=proof_graph.graph_hash,
        task_program_hash=task.oracle.task_program.program_hash,
        quality_contract_hash=quality_contract.contract_hash,
        expected_output_hash=canonical_hash(
            reference_trajectory.final_answer.get("result"), prefix="expected_output:"
        ),
        reference_execution_hash=reference_trajectory.trajectory_hash,
        operation_manifest_hash=canonical_hash(
            operation_registry.manifest(), prefix="operation_manifest:"
        ),
        counterfactual_operator_manifest_hash=(
            domain_plugin_set.counterfactual_operator_manifest_hash
            or canonical_hash((), prefix="counterfactual_operator_manifest:")
        ),
        domain_plugin_manifest_hash=canonical_hash(
            domain_plugin_set, prefix="domain_plugin_manifest:"
        ),
        source_grounding_manifest_hash=grounding_hash,
        task_pattern_hash=task_pattern_hash,
        evidence_binding_hash=evidence_binding_hash,
        task_pattern_compiler_version=task_pattern_compiler_version,
        compiler_version=compiler_version,
    )
