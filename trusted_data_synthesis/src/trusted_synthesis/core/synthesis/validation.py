from __future__ import annotations

import json

from trusted_synthesis.core.synthesis.schema import CompiledProofCarryingArtifacts


def validate_compiled_artifacts(artifacts: CompiledProofCarryingArtifacts) -> None:
    sample = artifacts.sample
    task = artifacts.task
    if sample.task_id != task.task_id or sample.task_package_hash != task.task_hash:
        raise ValueError("proof-carrying sample does not bind the task package")
    if (
        sample.evidence_bundle_id != artifacts.evidence_bundle.bundle_id
        or sample.evidence_bundle_hash != artifacts.evidence_bundle.bundle_hash
    ):
        raise ValueError("proof-carrying sample does not bind the evidence bundle")
    if (
        sample.proof_graph_id != artifacts.proof_graph.graph_id
        or sample.proof_graph_hash != artifacts.proof_graph.graph_hash
    ):
        raise ValueError("proof-carrying sample does not bind the proof graph")
    if (
        sample.reference_trajectory_id != artifacts.reference_trajectory.trajectory_id
        or sample.reference_trajectory_hash != artifacts.reference_trajectory.trajectory_hash
    ):
        raise ValueError("proof-carrying sample does not bind the reference trajectory")
    if (
        sample.quality_contract_id != artifacts.quality_contract.contract_id
        or sample.quality_contract_hash != artifacts.quality_contract.contract_hash
    ):
        raise ValueError("proof-carrying sample does not bind the quality contract")
    public_json = json.dumps(
        artifacts.public_artifact.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        sort_keys=True,
    )
    leaked = [item for item in task.oracle.gold_evidence_ids if item in public_json]
    if leaked:
        raise ValueError("public proof-carrying artifact leaks oracle evidence identities")
