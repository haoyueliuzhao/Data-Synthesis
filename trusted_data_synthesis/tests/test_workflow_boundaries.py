from __future__ import annotations

import inspect
import json

from trusted_synthesis.core.evidence.schema import EvidenceBundle, EvidenceItem
from trusted_synthesis.core.graph.builder import ProofGraphBuilder
from trusted_synthesis.core.operations.registry import default_registry
from trusted_synthesis.core.task.generator import ProofGraphTaskSynthesizer
from trusted_synthesis.runtime import CandidateTrajectoryGenerator, InMemoryEvidenceToolRuntime


def test_candidate_api_cannot_receive_an_oracle(finance_evidence: EvidenceItem) -> None:
    bundle = EvidenceBundle(
        bundle_id="bundle_boundary", evidence=(finance_evidence,), purpose="boundary test"
    )
    graph = ProofGraphBuilder().build(bundle)
    package = ProofGraphTaskSynthesizer().fact_retrieval(
        graph, bundle, finance_evidence.evidence_id
    )
    public_json = json.dumps(package.public.model_dump(mode="json"))
    runtime = InMemoryEvidenceToolRuntime(bundle)
    candidate = CandidateTrajectoryGenerator().generate(package.public, runtime)

    assert list(inspect.signature(CandidateTrajectoryGenerator.generate).parameters) == [
        "self",
        "task",
        "runtime",
    ]
    assert finance_evidence.evidence_id not in public_json
    assert runtime.last_query is not None
    assert "evidence_ids" not in runtime.last_query
    assert candidate.final_answer["result"]["payload"]["value"] == "383285"


def test_operation_registry_uses_separate_executor_and_oracle_modules() -> None:
    for item in default_registry().manifest():
        assert item["executor"]
        assert item["oracle_verifier"]
        definition = default_registry().require(str(item["operator_id"]))
        assert type(definition.executor).__module__ != type(definition.oracle_verifier).__module__
