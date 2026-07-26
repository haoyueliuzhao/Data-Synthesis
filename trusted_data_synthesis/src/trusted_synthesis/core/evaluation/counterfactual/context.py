from __future__ import annotations

from dataclasses import dataclass

from trusted_synthesis.core.evaluation.contracts.schema import QualityContract
from trusted_synthesis.core.evidence.corpus import EvidenceCorpus
from trusted_synthesis.core.graph.schema import ProofGraph
from trusted_synthesis.core.synthesis.schema import ProofCarryingSample
from trusted_synthesis.core.task.schema import TaskPackage
from trusted_synthesis.core.trajectory.schema import Trajectory


@dataclass(frozen=True)
class CounterfactualContext:
    source_sample: ProofCarryingSample
    task: TaskPackage
    contract: QualityContract
    corpus: EvidenceCorpus
    proof_graph: ProofGraph
    source_trajectory: Trajectory

    def validate(self) -> None:
        if self.source_sample.task_id != self.task.task_id:
            raise ValueError("counterfactual sample and task identities differ")
        if self.contract.task_id != self.task.task_id:
            raise ValueError("counterfactual contract and task identities differ")
        if self.source_trajectory.task_id != self.task.task_id:
            raise ValueError("counterfactual trajectory and task identities differ")
        if self.source_sample.quality_contract_hash != self.contract.contract_hash:
            raise ValueError("counterfactual sample does not bind the quality contract")
        if self.source_sample.proof_graph_hash != self.proof_graph.graph_hash:
            raise ValueError("counterfactual sample does not bind the proof graph")
        if self.source_sample.reference_trajectory_hash == self.source_trajectory.trajectory_hash:
            return
        if self.source_trajectory.workflow_kind.value != "candidate":
            raise ValueError("non-reference counterfactual sources must be candidate workflows")
